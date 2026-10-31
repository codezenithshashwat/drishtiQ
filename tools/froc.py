"""Lesion-level detection (ADR-031): sensitivity at 1, 2, 4 and 8 false-positive components per image, per lesion.

    .venv\\Scripts\\python tools\\froc.py            # the app's current segmenter (per lesion), IDRiD-val + DDR-test

Components are found at display size (long side 1024, as in the app) on the post-processed probability map binarised
at thresholds 0.05..0.95. A predicted component is a true positive if it overlaps a ground-truth component; a
ground-truth component is detected if any predicted component overlaps it. For each FP budget, the reported
sensitivity is the best over thresholds whose mean FP components per image stay within budget. Reported only.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference import postprocess as pp  # noqa: E402
from inference.pipeline import DISPLAY, LesionSegmenter, default_device  # noqa: E402

OUT = ROOT / "results/segmentation/froc.json"
THRESHOLDS = np.round(np.arange(0.05, 0.96, 0.05), 2)
BUDGETS = (1, 2, 4, 8)
LESIONS = ["MA", "HE", "EX", "SE"]


def main():
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    seg = LesionSegmenter(app, default_device())
    out = dict(segmenter=app.get("segmenter") or "v0 + pp_v2 (all lesions)", results={})
    for split in ("idrid_seg_val", "ddr_seg_test"):
        rows, _ = data.load_split(split)
        stats = {l: {t: [0, 0, 0] for t in THRESHOLDS} for l in LESIONS}  # [detected gt, total gt, fp components]
        n_img = {l: 0 for l in LESIONS}
        for r in rows:
            im = data.load_image(r["image_filepath"])
            scale = DISPLAY / max(im.size)
            size = (round(im.width * scale), round(im.height * scale))
            probs, _ = seg.masks(im, size, pp.locate_optic_disc(im))
            for l in LESIONS:
                if not r[f"{l}_mask"]:
                    continue
                truth = np.asarray(Image.fromarray(data.load_mask(r[f"{l}_mask"]).astype(np.uint8) * 255).resize(size, Image.Resampling.NEAREST)) > 0
                gt_lab, n_gt = ndi.label(truth, np.ones((3, 3)))
                n_img[l] += 1
                for t in THRESHOLDS:
                    lab, n = ndi.label(probs[l][0] >= t, np.ones((3, 3)))
                    hit_pred = np.unique(lab[truth & (lab > 0)])
                    hit_gt = np.unique(gt_lab[(lab > 0) & (gt_lab > 0)])
                    s = stats[l][t]
                    s[0] += len(hit_gt)
                    s[1] += n_gt
                    s[2] += n - len(hit_pred)
        res = {}
        for l in LESIONS:
            if not n_img[l]:
                continue
            curve = [dict(threshold=float(t), sensitivity=v[0] / max(v[1], 1), fp_per_image=v[2] / n_img[l]) for t, v in stats[l].items()]
            res[l] = dict(images=n_img[l], curve=curve, **{f"sens_at_{b}fp": max([c["sensitivity"] for c in curve if c["fp_per_image"] <= b] or [0.0])
                                                            for b in BUDGETS})
        out["results"][split] = res
        print(split, {l: {k: round(v, 3) for k, v in x.items() if k.startswith("sens")} for l, x in res.items()}, flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("RESULT: FROC written to results/segmentation/froc.json", flush=True)


if __name__ == "__main__":
    main()
