"""Audit and lock DeepDRiD regular fundus images (ADR-034, ADR-034a). No model is run on any image.

    .venv\\Scripts\\python tools\\audit_deepdrid.py

Writes data/interim/manifests/deepdrid_locked.json (the locked set, git-ignored) and
results/audit/deepdrid/audit_summary.json (counts, duplicates, leak matches; committed).
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from data.fingerprint import fingerprint, hamming_matrix, to_bits  # noqa: E402

BASE = ROOT / "data/raw/DeepDRiD/regular_fundus_images"
AUDIT = ROOT / "results/audit"
OUT_MANIFEST = ROOT / "data/interim/manifests/deepdrid_locked.json"
OUT_SUMMARY = AUDIT / "deepdrid/audit_summary.json"
FP_CACHE = AUDIT / "deepdrid/deepdrid_fingerprints.csv"


def read_csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def sheet(p):
    rows = list(openpyxl.load_workbook(p, read_only=True).active.iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:] if r and r[0] is not None]


def eye_grade(row):
    col = "left_eye_DR_Level" if "_l" in row["image_id"] else "right_eye_DR_Level"
    v = row.get(col)
    return int(float(v)) if v not in (None, "") else None


def collect():
    images = []
    for part, folder in (("training", "regular-fundus-training"), ("validation", "regular-fundus-validation")):
        for r in read_csv(BASE / folder / f"{folder}.csv"):
            path = BASE / folder / "Images" / r["patient_id"] / f"{r['image_id']}.jpg"
            images.append(dict(image_id=r["image_id"], patient_id=r["patient_id"], part=part, path=path.relative_to(ROOT).as_posix(),
                               grade=eye_grade(r), quality_ok=int(float(r["Overall quality"])) == 1))
    test = BASE / "Online-Challenge1&2-Evaluation"
    grades = {r["image_id"]: r["DR_Levels"] for r in sheet(test / "Challenge1_labels.xlsx")}
    quality = {r["image_id"]: r["Overall quality"] for r in sheet(test / "Challenge2_labels.xlsx")}
    for image_id in sorted(grades):
        pid = image_id.split("_")[0]
        path = test / "Images" / pid / f"{image_id}.jpg"
        images.append(dict(image_id=image_id, patient_id=pid, part="test", path=path.relative_to(ROOT).as_posix(),
                           grade=int(grades[image_id]) if grades[image_id] is not None else None, quality_ok=int(quality.get(image_id, 0)) == 1))
    return images


def main():
    images = collect()
    missing = [im["path"] for im in images if not (ROOT / im["path"]).exists()]
    on_disk = {p.relative_to(ROOT).as_posix() for p in BASE.rglob("*.jpg")}
    unlabelled = sorted(on_disk - {im["path"] for im in images})
    bad_grade = [im["image_id"] for im in images if im["grade"] is None or not 0 <= im["grade"] <= 5]

    FP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = {r["path"]: r for r in read_csv(FP_CACHE)} if FP_CACHE.exists() else {}
    for k, im in enumerate(images):
        if im["path"] not in cache and im["path"] not in missing:
            f = fingerprint(ROOT / im["path"])
            cache[im["path"]] = dict(path=im["path"], sha256=f["sha256"], shash=f["shash"])
        if (k + 1) % 250 == 0:
            print(f"hashed {k + 1}/{len(images)}", flush=True)
    with open(FP_CACHE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "sha256", "shash"])
        w.writeheader()
        w.writerows(cache.values())
    present = [im for im in images if im["path"] in cache]
    h = to_bits([cache[im["path"]]["shash"] for im in present])

    d = hamming_matrix(h, h)
    np.fill_diagonal(d, 999)
    dup_pairs = [(present[i]["image_id"], present[j]["image_id"], int(d[i, j])) for i, j in zip(*np.nonzero(np.triu(d <= 32)))]
    exact = Counter(cache[im["path"]]["sha256"] for im in present)

    refs = {}
    for name, f in (("IDRiD (all)", "aptos/idrid_all_fingerprints.csv"), ("APTOS train", "aptos/aptos_fingerprints.csv"),
                    ("APTOS test", "aptos/aptos_test_fingerprints.csv"), ("MMRDR", "mmrdr/mmrdr_cfp_fingerprints.csv"),
                    ("DDR lesion sets", "ddr/ddr_seg_fingerprints.csv")):
        p = AUDIT / f
        if p.exists():
            refs[name] = [r["shash"] for r in read_csv(p)]
    leak, leak_ids = {}, set()
    for name, ref in refs.items():
        dist = hamming_matrix(h, to_bits(ref)).min(1)
        hits = [present[i]["image_id"] for i in np.nonzero(dist <= 42)[0]]
        leak[name] = dict(reference_images=len(ref), matches=len(hits), examples=hits[:10])
        leak_ids |= set(hits)

    locked = [im for im in present if im["image_id"] not in leak_ids]
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(json.dumps(dict(adr=["ADR-034", "ADR-034a"], locked=True, source="github.com/deepdrdoc/DeepDRiD regular_fundus_images",
                                            licence="CC BY-SA 4.0", images=locked), indent=2))
    grades = Counter(im["grade"] for im in locked)
    summary = dict(images_labelled=len(images), patients=len({im["patient_id"] for im in images}), missing_files=missing, unlabelled_files=unlabelled,
                   invalid_grades=bad_grade, grade_counts={str(k): v for k, v in sorted(grades.items(), key=lambda t: (t[0] is None, t[0]))},
                   quality_ok=sum(im["quality_ok"] for im in locked), exact_duplicate_files=sum(v - 1 for v in exact.values() if v > 1),
                   near_duplicate_pairs_within_set=len(dup_pairs), near_duplicate_examples=dup_pairs[:10], leak_check=leak,
                   removed_for_leak=sorted(leak_ids), locked_images=len(locked),
                   locked_gradable=sum(1 for im in locked if im["grade"] is not None and im["grade"] <= 4))
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("near_duplicate_examples", "unlabelled_files", "missing_files")}, indent=2))
    print(f"RESULT: DeepDRiD audited and locked: {len(locked)} images ({summary['locked_gradable']} gradable), "
          f"{len(leak_ids)} removed by the leak check, {len(missing)} missing files, {len(unlabelled)} unlabelled files")


if __name__ == "__main__":
    main()
