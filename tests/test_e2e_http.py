"""End-to-end test over real HTTP: a fresh uvicorn process with a throwaway case store.

create case (upload + analyse) -> review (confirm) -> review (change stage, with reason) -> worklist shows Reviewed
-> report renders in English and Hindi. Also checks the regressions behind the 2026-10-29 405 bug: unknown /api/*
paths answer a JSON 404 for every method, and /api/version reports the commit the process runs.

    .venv\\Scripts\\python -m pytest tests\\test_e2e_http.py -q
"""
import csv
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = free_port()
    env = {**os.environ, "RS_DATA_DIR": str(tmp_path_factory.mktemp("e2e_store")), "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(port), "--app-dir", str(ROOT)],
                            env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(300):  # model loading can take minutes while the GPU queue is training
            try:
                if httpx.get(f"{base}/api/health", timeout=2).json().get("status") == "ok":
                    break
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
        else:
            pytest.fail("backend did not start within 300 s")
        c = httpx.Client(base_url=base, timeout=120, headers={"X-Requested-With": "dqn"})
        # V3: clinical endpoints need a signed-in ophthalmologist (the demo clinician seeded in demo mode; throwaway data dir).
        assert c.post("/api/network/auth/login", json={"identifier": "9000000004", "password": "Demo@Eye-Doctor1"}).status_code == 200
        yield c
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def training_image():
    """A clean IDRiD training image (never a validation, locked-test or Messidor-2 image)."""
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        path = next(csv.DictReader(f))["filepath"]
    return (ROOT / path).read_bytes()


def test_version_reports_commit(server):
    v = server.get("/api/version").json()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert v["commit"] == head and v["commit_on_disk"] == head and v["model_version"]


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_unknown_api_path_is_json_404(server, method):
    r = server.request(method, "/api/does-not-exist")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_full_flow(server):
    r = server.post("/api/cases", files={"file": ("eye.jpg", training_image(), "image/jpeg")}, data={"patient_ref": "E2E-1", "eye": "right"})
    assert r.status_code == 200, r.text
    case = r.json()
    cid, ai_stage = case["id"], case["analysis"]["grading"]["grade"]
    shape = set(server.get(f"/api/cases/{cid}").json())
    assert set(case) == shape and "patient" in shape  # every case endpoint returns the same record (a missing key crashed the page)
    assert case["status"] == "new"
    listed = server.get("/api/cases").json()["cases"]
    assert [c["id"] for c in listed] == [cid] and listed[0]["status"] == "new"

    r = server.post(f"/api/cases/{cid}/review", json={"decision": "agree", "note": "", "next_action": "follow_up"})
    assert r.status_code == 200 and r.json()["status"] == "reviewed"
    new_stage = (ai_stage + 1) % 5
    r = server.post(f"/api/cases/{cid}/review", json={"decision": "disagree", "corrected_stage": new_stage, "next_action": "referral",
                                                      "note": "More haemorrhages than the AI counted."})
    assert r.status_code == 200
    assert set(r.json()) == shape
    reviews = r.json()["reviews"]
    assert len(reviews) == 2 and reviews[0]["corrected_stage"] == new_stage and reviews[0]["note"].startswith("More")

    listed = server.get("/api/cases").json()["cases"]
    assert listed[0]["status"] == "reviewed"
    for kind, lang, needle in (("doctor", "en", "Screening report"), ("patient", "en", "Your eye screening result"), ("patient", "hi", "आपकी आँखों")):
        h = server.get(f"/api/patients/E2E-1/report.html", params={"kind": kind, "lang": lang})
        assert h.status_code == 200 and needle in h.text
    assert "More haemorrhages" in server.get("/api/patients/E2E-1/report.html", params={"kind": "doctor"}).text


def test_page_routes_still_serve_the_app(server):
    for path in ("/", "/cases/RS-1001", "/about"):
        r = server.get(path)
        assert r.status_code == 200 and "<div id=\"root\">" in r.text


def test_screening_camp_batch(server):
    """Several photographs in a row (as the batch upload sends them): good files become cases, a bad file fails alone."""
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        paths = [ROOT / r["filepath"] for _, r in zip(range(2), csv.DictReader(f))]
    before = len(server.get("/api/cases").json()["cases"])
    files = [("camp-001.jpg", paths[0].read_bytes()), ("camp-002.jpg", paths[1].read_bytes()), ("camp-003.jpg", paths[0].read_bytes()[:5000])]
    outcomes = []
    for name, blob in files:
        r = server.post("/api/cases", files={"file": (name, blob, "image/jpeg")}, data={"patient_ref": name.rsplit(".", 1)[0], "eye": "unknown"})
        outcomes.append((r.status_code, r.json()))
    assert [c for c, _ in outcomes] == [200, 200, outcomes[2][0]] and outcomes[2][0] in (415, 422)
    assert "image" in outcomes[2][1]["detail"].lower()
    listed = server.get("/api/cases").json()["cases"]
    assert len(listed) == before + 2 and {"camp-001", "camp-002"} <= {c["patient_ref"] for c in listed}


def test_disagreements_list_stage_changes(server):
    """After test_full_flow's stage change, the Disagreements view lists it with the reason."""
    d = server.get("/api/disagreements").json()
    hits = [x for x in d["disagreements"] if x["patient_ref"] == "E2E-1"]
    assert hits and hits[0]["note"].startswith("More haemorrhages") and hits[0]["corrected_stage"] != hits[0]["ai_stage"]
