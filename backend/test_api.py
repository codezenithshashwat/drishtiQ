"""API contract tests. Run: .venv\\Scripts\\python -m pytest backend -q"""
import csv
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import store
from backend.app import ROOT, app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Cases go to a throwaway store, never the local worklist.
    tmp = tmp_path_factory.mktemp("store")
    old = store.DIR, store.IMAGES
    store.DIR, store.IMAGES = tmp, tmp / "images"
    with TestClient(app) as c:
        yield c
    store.DIR, store.IMAGES = old


def encode(arr, fmt="PNG"):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return buf.getvalue()


def test_health_and_version(client):
    assert client.get("/api/health").json()["status"] == "ok"
    files = client.get("/api/version").json()["checkpoints_sha256"]
    assert any(k.endswith(".json") for k in files) and len(files) >= 3  # grader + segmenter weights + post-processing config


def test_rejects_non_image(client):
    r = client.post("/api/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_rejects_tiny_image(client):
    r = client.post("/api/analyze", files={"file": ("x.png", encode(np.zeros((64, 64, 3), np.uint8)), "image/png")})
    assert r.status_code == 422


def test_black_image_is_rejected_by_quality_gate(client):
    r = client.post("/api/analyze", files={"file": ("x.png", encode(np.zeros((600, 800, 3), np.uint8)), "image/png")})
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_fundus_response_schema(client):
    # A clean *training* image; the locked clean test set is never used here.
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        path = next(csv.DictReader(f))["filepath"]
    r = client.post("/api/analyze", files={"file": ("f.jpg", (ROOT / path).read_bytes(), "image/jpeg")})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok"
    g = body["grading"]
    assert 0 <= g["grade"] <= 4 and abs(sum(g["probabilities"]) - 1) < 1e-4 and g["calibrated"] is False
    assert [l["key"] for l in body["lesions"]] == ["MA", "HE", "EX", "SE"]
    assert body["attribution"]["overlay"] and body["disclaimer"]


def train_image():
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        return (ROOT / next(csv.DictReader(f))["filepath"]).read_bytes()


def test_case_review_report_flow(client):
    r = client.post("/api/cases", files={"file": ("f.jpg", train_image(), "image/jpeg")}, data={"patient_ref": "TEST-1", "eye": "left"})
    assert r.status_code == 200
    case = r.json()
    assert case["id"].startswith("RS-") and case["analysis"]["status"] == "ok" and "defer" in case["assist"]
    rows = client.get("/api/cases").json()["cases"]
    assert [c["id"] for c in rows] == [case["id"]]
    assert client.post(f"/api/cases/{case['id']}/review", json={"reviewer": "T", "decision": "disagree"}).status_code == 422
    r = client.post(f"/api/cases/{case['id']}/review", json={"reviewer": "T", "decision": "disagree", "corrected_stage": 2, "note": "x"})
    assert r.status_code == 200 and r.json()["status"] == "reviewed" and r.json()["reviews"][0]["corrected_stage"] == 2
    detail = client.get(f"/api/cases/{case['id']}").json()
    assert detail["patient"]["follow_up"]["level"] in {"routine", "refer", "urgent", "human", "retake", "incomplete"}
    for kind, lang, needle in (("doctor", "en", "Screening report"), ("patient", "en", "Your eye screening result"), ("patient", "hi", "आपकी आँखों")):
        h = client.get(f"/api/patients/TEST-1/report.html?kind={kind}&lang={lang}")
        assert h.status_code == 200 and needle in h.text
    assert client.get("/api/patients/TEST-1/report.html?kind=patient&lang=fr").status_code == 422
    assert "corrected_stage" in client.get("/api/feedback.csv").text


def test_case_validation(client):
    bad_eye = client.post("/api/cases", files={"file": ("f.jpg", train_image(), "image/jpeg")}, data={"patient_ref": "T", "eye": "middle"})
    assert bad_eye.status_code == 422
    assert client.get("/api/cases/RS-9999").status_code == 404


def test_model_card(client):
    m = client.get("/api/model").json()
    assert m["grader"] and m["dme_rule"]["min_exudate_area_px"] > 0 and m["checkpoints"]


def test_corrupt_image_gets_plain_message(client):
    # A JPEG cut off half-way passes the header check but cannot be decoded.
    data = train_image()
    r = client.post("/api/analyze", files={"file": ("cut.jpg", data[: len(data) // 2], "image/jpeg")})
    assert r.status_code in (415, 422) and "image" in r.json()["detail"].lower()


def test_unknown_api_path_is_json_404(client):
    for method in ("get", "post"):
        r = getattr(client, method)("/api/nope")
        assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
