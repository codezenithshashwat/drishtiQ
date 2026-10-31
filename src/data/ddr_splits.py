"""DDR segmentation split policy (A3): train on DDR train + valid; keep DDR official test as a second segmentation
validation set (never trained on). Input is the audited, protection-filtered manifest from audit_ddr.py.
    .venv\\Scripts\\python src\\data\\ddr_splits.py   -> configs/splits/ddr_seg_trainval.csv, ddr_seg_test.csv
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "configs/splits/ddr_seg_all.csv"


def main():
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {"ddr_seg_trainval": [r for r in rows if r["ddr_split"] in ("train", "valid")],
           "ddr_seg_test": [r for r in rows if r["ddr_split"] == "test"]}
    for name, part in out.items():
        path = ROOT / f"configs/splits/{name}.csv"
        if path.exists():
            sys.exit(f"{path.name} already frozen")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(part)
        print(name, len(part), dict(Counter(r["ddr_split"] for r in part)))


if __name__ == "__main__":
    main()
