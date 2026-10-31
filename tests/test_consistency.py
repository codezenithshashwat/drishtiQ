"""Every number the About page shows must trace to results/registry.csv or a recorded decision/config file.

The About page renders /api/model; this test recomputes each value from its source and compares.
"""
import csv
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def card(tmp_path_factory):
    from backend import store
    from backend.app import app
    old = store.DIR, store.IMAGES
    tmp = tmp_path_factory.mktemp("store")
    store.DIR, store.IMAGES = tmp, tmp / "images"
    with TestClient(app) as c:
        yield c.get("/api/model").json()
    store.DIR, store.IMAGES = old


def registry():
    with open(ROOT / "results/registry.csv", encoding="utf-8") as f:
        return {r["run_id"]: r for r in csv.DictReader(f)}


def test_grading_numbers_come_from_registry(card):
    reg = registry()
    for key, split in (("idrid_val", "idrid_grading_val"), ("aptos_val", "aptos_val")):
        g = card["grading"][key]
        assert g, f"no registered run for the app grader on {split}"
        row = reg[g["run_id"]]
        assert row["model"] == card["system_name"] and row["eval_split"] == split
        for metric in ("qwk", "macro_f1", "severe_under", "referable_sens", "referable_spec", "recall_g1"):
            assert abs(float(row[metric]) - g["point"][metric]) <= 5e-5, (split, metric)  # registry stores 4 decimals
        metrics = json.loads((ROOT / "results/runs" / g["run_id"] / "metrics.json").read_text())
        assert metrics["confusion"] == g["confusion"]


def test_segmentation_numbers_come_from_registry(card):
    reg = registry()
    for model, splits in card["segmentation"].items():
        for split, row in splits.items():
            if row is None:
                continue
            src = reg[row["run_id"]]
            assert src["model"] == model and src["eval_split"] == split
            assert all(src[k] == v for k, v in row.items())


def test_dme_rule_numbers_come_from_its_file_and_registry(card):
    rule = json.loads((ROOT / card["dme_rule"]["file"]).read_text())
    assert card["dme_rule"]["val"] == rule["val"] and card["dme_rule"]["min_exudate_area_px"] == rule["min_exudate_area_px"]
    name = Path(card["dme_rule"]["file"]).stem
    rows = [r for r in registry().values() if r["task"] == "dme-rule" and r["model"] == name]
    assert rows and abs(float(rows[-1]["macro_f1"]) - rule["val"]["macro_f1"]) <= 5e-5


def test_calibration_numbers_come_from_a_recorded_decision(card):
    cal = card["calibration"]
    if cal is None:
        pytest.skip("calibration not fitted for the current grader")
    assert cal == json.loads((ROOT / "configs/calibration/app_grader.json").read_text())
    recorded = [json.loads(p.read_text()) for p in (ROOT / "queue/decisions").glob("assistant_metrics_*.json")]
    assert any(r == cal for r in recorded), "calibration file differs from every recorded queue decision"


def test_step4_verdicts_come_from_result_files(card):
    """ADR-041: About-page verdicts match the pre-registered rule outcomes in the result files; registry rows exist."""
    path = ROOT / "results/step4/step4_results.json"
    if not path.exists():
        pytest.skip("Step 4 not run")
    res = json.loads(path.read_text())
    rows = {e["key"]: e for e in card["experiments"]}
    expect = {"disagreement": res["a_disagreement"]["rule"]["verdict"], "ood": res["b_ood"]["rule"]["verdict"],
              "referable_head": res["c_referable_head"]["primary_head_vs_pinned"]["rule"]["verdict"]}
    for key, verdict in expect.items():
        assert rows[key]["verdict"] == ("abandon" if verdict == "ABANDON" else "adopt"), key
    assert rows["ensemble"]["verdict"] == "not testable"  # owner rule: fewer than two extra seeds
    step4 = [r for r in registry().values() if r["task"] == "step4"]
    assert {r["model"] for r in step4} >= {"step4:disagreement", "step4:ood", "step4:referable_head", "step4:ensemble"}


def test_coverage_numbers_come_from_registry_and_routing_config(card):
    """Routine-rescreening coverage (ADR-039/040): registry rows, their metrics.json and configs/routing/routing_v1.json agree."""
    cov = card["coverage"]
    assert cov, "no registered coverage run"
    reg = registry()
    cfg = json.loads((ROOT / "configs/routing/routing_v1.json").read_text())
    assert cov["thresholds"] == cfg["thresholds"]
    for run_id in cov["run_ids"]:
        row = reg[run_id]
        name = {"idrid_grading_val": "IDRiD-val", "aptos_val": "APTOS-val"}[row["eval_split"]]
        v = cov["sets"][name]["0.025"]
        assert int(row["n_images"]) == v["units"] and f"coverage {v['coverage']:.4f}" in row["notes"]
        assert f"miss {v['missed']}/{v['referable']}" in row["notes"]
    for lvl, sets in cfg["verified"].items():
        for name, v in sets.items():
            c = cov["sets"][name][lvl]
            assert (c["coverage"], c["missed"], c["referable"], c["miss_rate_upper95"]) == (v["coverage"], v["missed"], v["referable"], v["upper95"])
    assert f"{cfg['verified'][str(cov['target'])]['APTOS-val']['upper95'] * 100:.1f}%" in cov["wording"]


def test_swap_decisions_are_recorded(card):
    for name, d in card["decisions"].items():
        assert json.loads((ROOT / f"queue/decisions/{name}.json").read_text()) == d


def test_agreement_numbers_recompute_from_predictions(card):
    import numpy as np
    sys.path.insert(0, str(ROOT / "src"))
    from eval import metrics
    reg = registry()
    for key, split in (("idrid_val", "idrid_grading_val"), ("aptos_val", "aptos_val")):
        a = card["agreement"][key]
        assert a and reg[a["run_id"]]["task"] == "agreement" and reg[a["run_id"]]["eval_split"] == split
        src = reg[a["source_run"]]
        assert src["model"] == card["system_name"] and src["eval_split"] == split
        preds = list(csv.DictReader(open(next((ROOT / "results/runs" / a["source_run"]).glob("predictions_*.csv")), encoding="utf-8")))
        point = metrics._point(np.array([int(r["DR_grade"]) for r in preds]), np.array([int(r["predicted"]) for r in preds]))
        for k, v in a["point"].items():
            assert abs(point[k] - v) < 1e-12, (split, k)


def test_key_numbers_file_is_generated_and_current():
    """results/KEY_NUMBERS.md must equal a fresh generation from the registry and decision files (never hand-edited)."""
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools/key_numbers.py"), "--check"], cwd=ROOT)
    assert r.returncode == 0, "results/KEY_NUMBERS.md is stale: run tools/key_numbers.py"


def test_scorecard_is_generated_and_current():
    """results/SCORECARD.md must equal a fresh generation (targets from ADR-026, values from recorded results)."""
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools/scorecard.py"), "--check"], cwd=ROOT)
    assert r.returncode == 0, "results/SCORECARD.md is stale: run tools/scorecard.py"


def test_models_compared_come_from_registry(card):
    reg = registry()
    assert len(card["compared"]) >= 4
    for c in card["compared"]:
        for key in ("idrid_val", "aptos_val"):
            if c[key]:
                assert abs(float(reg[c[key]["run_id"]]["qwk"]) - c[key]["qwk"]) < 1e-12


def test_reproduce_script_passes():
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools/reproduce.py"), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
