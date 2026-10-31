"""Reproduce the reported numbers from saved predictions (no retraining, no inference). Run via reproduce.ps1.

    .venv\\Scripts\\python tools\\reproduce.py           # verify, then rewrite KEY_NUMBERS.md and SCORECARD.md
    .venv\\Scripts\\python tools\\reproduce.py --check   # verify only; exit 1 on any mismatch (used by the tests)

1. Model/config checksums against configs/app/checksums.json (when recorded).
2. For every grading run the reports use (the app system's latest runs, agreement sources, models compared), the
   metrics are recomputed from the run's predictions file and compared with results/registry.csv.
3. KEY_NUMBERS.md and SCORECARD.md are regenerated and compared with the committed files.
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import metrics  # noqa: E402

problems = []


def say(ok, msg):
    print(f"[{'PASS' if ok else 'FAIL'}] {msg}", flush=True)
    if not ok:
        problems.append(msg)


def main():
    check = "--check" in sys.argv
    man = ROOT / "configs/app/checksums.json"
    if man.exists():
        rec = json.loads(man.read_text())
        bad = [k for k, v in rec.items() if not (ROOT / k).exists() or hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != v]
        say(not bad, f"checksums of {len(rec)} recorded files" + (f": changed {bad}" if bad else ""))
    else:
        print("[INFO] no recorded checksums yet (recorded at rc-1)")

    rows = {r["run_id"]: r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8"))}
    card = None
    try:
        from fastapi.testclient import TestClient  # the About page's own numbers
        sys.path.insert(0, str(ROOT))
        import os
        import tempfile
        os.environ.setdefault("RS_DATA_DIR", tempfile.mkdtemp())
        from backend.app import app
        with TestClient(app) as c:
            card = c.get("/api/model").json()
    except Exception as e:  # noqa: BLE001
        say(False, f"could not build the model card ({e})")
    runs = set()
    if card:
        runs |= {g["run_id"] for g in card["grading"].values() if g}
        runs |= {a["source_run"] for a in card["agreement"].values() if a}
        runs |= {x["run_id"] for c in card["compared"] for x in (c["idrid_val"], c["aptos_val"]) if x}
    for run in sorted(runs):
        preds = list(csv.DictReader(open(next((ROOT / "results/runs" / run).glob("predictions_*.csv")), encoding="utf-8")))
        p = metrics._point(np.array([int(r["DR_grade"]) for r in preds]), np.array([int(r["predicted"]) for r in preds]))
        reg = rows[run]
        diffs = [k for k in ("qwk", "macro_f1", "recall_g1", "severe_under", "referable_sens", "referable_spec")
                 if reg.get(k) not in ("", None) and abs(float(reg[k]) - p[k]) > 5e-5]
        say(not diffs, f"{run}: metrics recomputed from {len(preds)} predictions" + (f" differ in {diffs}" if diffs else " match the registry"))

    for tool, out in (("key_numbers.py", "results/KEY_NUMBERS.md"), ("scorecard.py", "results/SCORECARD.md")):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / tool), "--check"], cwd=ROOT)
        if r.returncode and not check:
            subprocess.run([sys.executable, str(ROOT / "tools" / tool)], cwd=ROOT, check=True)
            print(f"[INFO] {out} regenerated (it was out of date)")
        else:
            say(r.returncode == 0, f"{out} equals a fresh generation")
    print("\nRESULT:", "reproduced" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
