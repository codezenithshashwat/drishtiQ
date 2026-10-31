"""Cleaned MMRDR-CFP training manifest (approved rules): tr + ts, conflicting-label duplicate groups dropped, one image
kept per consistent duplicate group, and any image within the review band of an IDRiD image (all tasks/splits, incl.
locked) or an APTOS-val image dropped so no near-copy of a validation/locked image enters training.

    .venv\\Scripts\\python src\\data\\mmrdr_manifest.py      -> configs/splits/mmrdr_train.csv
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.audit_aptos import REVIEW_HAMMING, read_csv, write_csv  # noqa: E402
from data.fingerprint import hamming_matrix, to_bits  # noqa: E402

AUDIT = ROOT / "results/audit"
OUT = ROOT / "configs/splits/mmrdr_train.csv"


def main():
    if OUT.exists():
        raise SystemExit("mmrdr_train.csv already frozen")
    rows = read_csv(AUDIT / "mmrdr/mmrdr_cfp_fingerprints.csv")
    index = {r["image"]: i for i, r in enumerate(rows)}
    groups = {}
    for g in read_csv(AUDIT / "mmrdr/mmrdr_cfp_duplicate_groups.csv"):
        groups.setdefault(g["group"], []).append(index[g["image"]])
    drop = {}
    for members in groups.values():
        if len({rows[i]["DR_grade"] for i in members}) > 1:
            drop.update({i: "duplicate_group_conflicting_labels" for i in members})
        else:
            best = max(members, key=lambda i: int(rows[i]["width"]) * int(rows[i]["height"]))
            drop.update({i: "redundant_duplicate_same_label" for i in members if i != best})

    h = to_bits([r["shash"] for r in rows])
    protected = read_csv(AUDIT / "aptos/idrid_all_fingerprints.csv")
    aptos_val = {r["id_code"] for r in read_csv(ROOT / "configs/splits/aptos_val.csv")}
    protected += [r for r in read_csv(AUDIT / "aptos/aptos_fingerprints.csv") if r["id_code"] in aptos_val]
    hp = to_bits([r["shash"] for r in protected])
    sha_p = {r["sha256"] for r in protected}
    for start in range(0, len(rows), 2000):
        near = hamming_matrix(h[start:start + 2000], hp).min(1) <= REVIEW_HAMMING
        for k in np.flatnonzero(near):
            drop.setdefault(start + int(k), "near_copy_of_validation_or_locked_image")
    for i, r in enumerate(rows):
        if r["sha256"] in sha_p:
            drop.setdefault(i, "exact_copy_of_validation_or_locked_image")

    kept = [dict(id_code=Path(r["image"]).stem, filepath=r["path"], DR_grade=r["DR_grade"], content_hash=r["sha256"], source_split=r["split"])
            for i, r in enumerate(rows) if i not in drop]
    write_csv(OUT, kept, ["id_code", "filepath", "DR_grade", "content_hash", "source_split"])
    summary = dict(images=len(rows), dropped=dict(Counter(drop.values())), kept=len(kept),
                   kept_grades=dict(sorted(Counter(r["DR_grade"] for r in kept).items())),
                   kept_by_source_split=dict(Counter(r["source_split"] for r in kept)))
    (AUDIT / "mmrdr/mmrdr_train_manifest_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
