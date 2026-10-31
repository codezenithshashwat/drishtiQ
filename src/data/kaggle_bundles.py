"""Build private-Kaggle-dataset upload folders (outside git) with hash manifests.

    .venv\\Scripts\\python src\\data\\kaggle_bundles.py idrid-dev
    .venv\\Scripts\\python src\\data\\kaggle_bundles.py mmrdr-cfp

Files are hard links to the raw data (no extra disk space; raw stays read-only). idrid-dev contains only the
404 clean grading-train images and the 50 development segmentation images with their masks, and is verified
against every locked test image by file SHA-256 and by decoded-pixel hash.
"""
import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402

UPLOAD = ROOT / "kaggle_upload"
LICENCE = {"idrid-dev": "CC-BY-4.0", "mmrdr-cfp": "CC-BY-4.0"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        os.link(src, dst)


def metadata(folder, slug, title, files):
    (folder / "dataset-metadata.json").write_text(json.dumps({
        "title": title, "id": f"<your-kaggle-username>/{slug}", "licenses": [{"name": LICENCE[slug]}]}, indent=2))
    with open(folder / "MANIFEST.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "bytes", "sha256"])
        for p in files:
            w.writerow([p.relative_to(folder).as_posix(), p.stat().st_size, sha(p)])


def idrid_dev():
    folder = UPLOAD / "idrid-dev"
    if folder.exists():
        shutil.rmtree(folder)
    # Locked material: the clean grading test, the quarantined conflicting-label images, and the official segmentation
    # test. Redundant agreeing duplicates are not locked: their identical twin is a kept dev image.
    excluded = data.read_csv(ROOT / "data/interim/manifests/idrid_grading_excluded.csv")
    locked_rows = data.read_csv(ROOT / "data/interim/manifests/idrid_grading_test_clean.csv") + \
        [r for r in excluded if r["duplicate_status"] == "conflicting_labels"]
    locked_file_sha = {r["file_sha256"] for r in locked_rows}
    locked_content = {r["content_hash"] for r in locked_rows}
    seg_test = [r for r in data.read_csv(data.SEG_ANNOTATIONS) if r["original_split"] == "test"]
    locked_file_sha |= {sha(ROOT / r["image_filepath"]) for r in {r["image_filepath"]: r for r in seg_test}.values()}
    locked_content |= {r["image_content_hash"] for r in seg_test}

    files = []
    split_files = ["idrid_grading_devtrain", "idrid_grading_val", "idrid_seg_train", "idrid_seg_val"]
    grading = data.load_split("idrid_grading_devtrain")[0] + data.load_split("idrid_grading_val")[0]
    for r in grading:
        assert r["content_hash"] not in locked_content
        dst = folder / "grading" / Path(r["filepath"]).name
        link(ROOT / r["filepath"], dst)
        files.append(dst)
    seg = data.load_split("idrid_seg_train")[0] + data.load_split("idrid_seg_val")[0]
    for r in seg:
        assert r["image_content_hash"] not in locked_content
        dst = folder / "segmentation/images" / Path(r["image_filepath"]).name
        link(ROOT / r["image_filepath"], dst)
        files.append(dst)
        for lesion in data.LESIONS:
            if r[f"{lesion}_mask"]:
                dst = folder / "segmentation/masks" / lesion / Path(r[f"{lesion}_mask"]).name
                link(ROOT / r[f"{lesion}_mask"], dst)
                files.append(dst)
    for name in split_files:
        dst = folder / "splits" / f"{name}.csv"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data.SPLITS / f"{name}.csv", dst)
        files.append(dst)
    leaked = [p for p in files if sha(p) in locked_file_sha]
    if leaked:
        raise SystemExit(f"LOCKED TEST FILES FOUND: {leaked}")
    metadata(folder, "idrid-dev", "IDRiD dev (no locked test)", files)
    print(f"idrid-dev: {len(files)} files; 0 matches against {len(locked_file_sha)} locked file hashes "
          f"and {len(locked_content)} locked content hashes")


def mmrdr_cfp():
    src = ROOT / "data/raw/MMRDR/MMRDR-CFP"
    folder = UPLOAD / "mmrdr-cfp"
    files = []
    for p in sorted(src.rglob("*")):
        if p.is_file():
            dst = folder / p.relative_to(src)
            link(p, dst)
            files.append(dst)
    metadata(folder, "mmrdr-cfp", "MMRDR-CFP (Tang et al. 2026)", files)
    print(f"mmrdr-cfp: {len(files)} files")


if __name__ == "__main__":
    {"idrid-dev": idrid_dev, "mmrdr-cfp": mmrdr_cfp}[sys.argv[1]]()
