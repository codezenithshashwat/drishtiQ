"""Make sure the current app grader has agreement rows (exact / within one stage, ADR-013 operating point) for its latest
grading run on IDRiD-val and APTOS-val; computes only what is missing (CPU, from prediction files).

    .venv\Scripts\python tools\agreement_app.py
"""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inference.system import system_name  # noqa: E402


def main():
    spec = system_name(json.loads((ROOT / "configs/app/app.json").read_text()))
    rows = list(csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8")))
    done = {json.loads((ROOT / "results/runs" / r["run_id"] / "metrics.json").read_text())["source_run"]
            for r in rows if r["task"] == "agreement" and r["model"] == spec}
    for split in ("idrid_grading_val", "aptos_val"):
        runs = [r["run_id"] for r in rows if r["task"] == "grade" and r["model"] == spec and r["eval_split"] == split]
        if not runs:
            print(f"no grading run of {spec} on {split}; run the harness first")
            continue
        if runs[-1] not in done:
            subprocess.run([sys.executable, "-m", "eval", "agreement", "--run", runs[-1]], cwd=ROOT, check=True,
                           env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    print("RESULT: agreement rows up to date for the app grader", flush=True)


if __name__ == "__main__":
    main()
