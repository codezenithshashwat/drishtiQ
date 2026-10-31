"""Frozen evaluation splits and image/mask loading. Splits hold image IDs and paths only (no pixels).

Uses the csv module rather than pandas: on this machine Windows Smart App Control blocks pandas'
compiled extensions, and the harness must keep running regardless.
"""
import csv
import hashlib
import json

import numpy as np
from PIL import Image, ImageOps
from sklearn.model_selection import StratifiedShuffleSplit

from . import ROOT

SPLITS = ROOT / "configs" / "splits"
LESIONS = ["MA", "HE", "EX", "SE"]
SPLIT_SEED = 20261028
GRADING_TRAIN_MANIFEST = ROOT / "data/interim/manifests/idrid_grading_train_clean.csv"
SEG_DEV_SPLIT = ROOT / "outputs/metrics/model_selection/segmentation_development_split.csv"
SEG_ANNOTATIONS = ROOT / "outputs/metrics/idrid_segmentation_annotation_policy.csv"


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def make_splits():
    """Create the frozen splits once. Refuses to overwrite existing split files."""
    SPLITS.mkdir(parents=True, exist_ok=True)
    targets = {k: SPLITS / f"{k}.csv" for k in ["idrid_grading_devtrain", "idrid_grading_val", "idrid_seg_train", "idrid_seg_val"]}
    existing = [p.name for p in targets.values() if p.exists()]
    if existing:
        raise SystemExit(f"Splits already frozen ({', '.join(existing)}); delete deliberately to regenerate.")

    # Grading: stratified 75/25 split of the 404-image clean IDRiD training pool. The clean test set is not read.
    g = read_csv(GRADING_TRAIN_MANIFEST)
    assert len(g) == 404 and len({r["content_hash"] for r in g}) == 404
    grades = np.array([int(r["DR_grade"]) for r in g])
    tr, va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.25, random_state=SPLIT_SEED).split(grades, grades))
    cols = ["sample_key", "image_id", "filepath", "DR_grade", "content_hash"]
    for idx, key in [(tr, "idrid_grading_devtrain"), (va, "idrid_grading_val")]:
        write_csv(targets[key], sorted((g[i] for i in idx), key=lambda r: r["image_id"]), cols)

    # Segmentation: reuse the model-selection 40/10 split so v0 segmenters are evaluated on images they never saw.
    seg = read_csv(SEG_DEV_SPLIT)
    masks = {}
    for a in read_csv(SEG_ANNOTATIONS):
        if a["annotation_available"] == "True":
            masks[(a["sample_key"], a["annotation_type"])] = a["mask_filepath"]
    for r in seg:
        for lesion in LESIONS:
            r[f"{lesion}_mask"] = masks.get((r["sample_key"], lesion), "")
    cols = ["sample_key", "image_id", "image_filepath", "image_content_hash"] + [f"{l}_mask" for l in LESIONS]
    for role, key in [("train", "idrid_seg_train"), ("validation", "idrid_seg_val")]:
        write_csv(targets[key], sorted((r for r in seg if r["role"] == role), key=lambda r: r["image_id"]), cols)

    manifest = {p.name: file_sha(p) for p in targets.values()}
    manifest["seed"] = SPLIT_SEED
    (SPLITS / "SPLITS.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_split(name):
    path = SPLITS / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"Missing split {path}; run `python -m eval make-splits` first.")
    return read_csv(path), file_sha(path)


def load_image(rel_path):
    with Image.open(ROOT / rel_path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def load_mask(rel_path):
    """Binary mask from an IDRiD ground-truth file; alpha is ignored (one EX mask is RGBA)."""
    with Image.open(ROOT / rel_path) as im:
        a = np.asarray(im)
    a = a[..., :3] if a.ndim == 3 else a
    b = a > 0
    return b.any(2) if b.ndim == 3 else b
