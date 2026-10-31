"""DDR lesion-segmentation subset: audit (counts, resolutions, mask encoding, lesion prevalence) and overlap check
(calibrated structure hash, same rules as APTOS/MMRDR) against MMRDR-CFP, IDRiD (all, incl. locked) and APTOS.
Writes the audited manifest configs/splits/ddr_seg_all.csv (DDR = training side only; all three DDR splits used).

DDR annotated all four lesions on every image, so an empty DDR mask is an annotated negative (unlike IDRiD, where a
missing mask file means "not annotated").
    .venv\\Scripts\\python src\\data\\audit_ddr.py
"""
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data.audit_aptos import DUP_HAMMING, REVIEW_HAMMING, _fp, contact_sheet, read_csv, write_csv  # noqa: E402
from data.fingerprint import hamming_matrix, to_bits  # noqa: E402

RAW = ROOT / "data/raw/DDR/lesion_segmentation"
OUT = ROOT / "results/audit/ddr"
SHEETS = ROOT / "results/audit_images/ddr"
LESIONS = ["MA", "HE", "EX", "SE"]
LABEL_DIR = {"train": "label", "valid": "segmentation label", "test": "label"}


def mask_stats(args):
    split, stem = args
    out = dict(split=split, image_id=stem)
    for lesion in LESIONS:
        path = RAW / split / LABEL_DIR[split] / lesion / f"{stem}.tif"
        with Image.open(path) as m:
            a = np.asarray(m)
            out[f"{lesion}_mode"] = m.mode
        values = np.unique(a)
        b = a > 0
        out[f"{lesion}_values"] = " ".join(map(str, values[:4]))
        out[f"{lesion}_pixels"] = int(b.sum())
        out[f"{lesion}_components"] = int(ndi.label(b, np.ones((3, 3)))[1])
        out[f"{lesion}_mask"] = str(path.relative_to(ROOT)).replace("\\", "/")
    return out


def main():
    items = [(s, p.stem) for s in ("train", "valid", "test") for p in sorted((RAW / s / "image").glob("*.jpg"))]
    images = [RAW / s / "image" / f"{stem}.jpg" for s, stem in items]
    with ProcessPoolExecutor(6) as ex:
        stats = list(ex.map(mask_stats, items, chunksize=8))
        fps = list(ex.map(_fp, images, chunksize=8))
    rows = [dict(s, **f) for s, f in zip(stats, fps)]
    write_csv(OUT / "ddr_seg_fingerprints.csv", rows)

    h = to_bits([r["shash"] for r in rows])
    internal = hamming_matrix(h, h)
    np.fill_diagonal(internal, 999)
    internal_dups = [(i, j, int(internal[i, j])) for i, j in zip(*np.nonzero(internal <= DUP_HAMMING)) if i < j]
    others = {"MMRDR-CFP": read_csv(ROOT / "results/audit/mmrdr/mmrdr_cfp_fingerprints.csv"),
              "IDRiD_all": read_csv(ROOT / "results/audit/aptos/idrid_all_fingerprints.csv"),
              "APTOS_all": read_csv(ROOT / "results/audit/aptos/aptos_fingerprints.csv")}
    aptos_val = {r["id_code"] for r in read_csv(ROOT / "configs/splits/aptos_val.csv")}
    overlap, drop = {}, {}
    for name, other in others.items():
        d = hamming_matrix(h, to_bits([r["shash"] for r in other]))
        sha = {r["sha256"] for r in other}
        nearest = d.min(1)
        overlap[name] = dict(exact=sum(r["sha256"] in sha for r in rows),
                             within_dup_threshold=int((nearest <= DUP_HAMMING).sum()),
                             within_review_band=int((nearest <= REVIEW_HAMMING).sum()))
        for k, i in enumerate(np.argsort(nearest)[:4]):
            j = int(d[i].argmin())
            contact_sheet(SHEETS / f"vs_{name}_{k}.jpg", [(rows[i]["path"], "DDR"), (other[j]["path"], name)], f"hamming {int(nearest[i])}")
        if name in ("IDRiD_all", "APTOS_all"):  # protect validation and locked images (conservative band)
            for i in np.flatnonzero(nearest <= REVIEW_HAMMING):
                j = int(d[i].argmin())
                if name == "IDRiD_all" or other[j].get("id_code") in aptos_val:
                    drop[int(i)] = f"near_copy_of_{name}"

    report = dict(images=len(rows), by_split=dict(Counter(r["split"] for r in rows)),
                  resolutions=Counter(f"{r['width']}x{r['height']}" for r in rows).most_common(8),
                  mask_modes=dict(Counter(r["MA_mode"] for r in rows)), mask_values_examples=sorted({r["MA_values"] for r in rows})[:4],
                  images_with_lesion={l: sum(r[f"{l}_pixels"] > 0 for r in rows) for l in LESIONS},
                  components_total={l: sum(r[f"{l}_components"] for r in rows) for l in LESIONS},
                  internal_duplicate_pairs=len(internal_dups), overlap=overlap, dropped_for_protection=len(drop),
                  empty_mask_semantics="annotated negative (DDR annotated all four lesions per image)",
                  licence="CC BY-NC-SA 4.0")
    (OUT / "ddr_seg_audit.json").write_text(json.dumps(report, indent=2))
    keep = [dict(image_id=r["image_id"], ddr_split=r["split"], image_filepath=r["path"], image_content_hash=r["sha256"],
                 **{f"{l}_mask": r[f"{l}_mask"] for l in LESIONS}) for i, r in enumerate(rows) if i not in drop]
    write_csv(ROOT / "configs/splits/ddr_seg_all.csv", keep,
              ["image_id", "ddr_split", "image_filepath", "image_content_hash"] + [f"{l}_mask" for l in LESIONS])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
