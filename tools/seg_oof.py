"""Out-of-fold IDRiD maps for a segmentation candidate that has no CV maps of its own (ADR-031a).

    .venv\Scripts\python tools\seg_oof.py --kind a3tta --out results/cache/seg_a3tta_cv

For fold k, the fold-k A3 model (never trained on fold k) with horizontal-flip TTA maps the fold-k images. The folds are
the v0/A3 assignment (results/cache/segcv/folds.json). Output: <image_id>.npz (maps, box), as seg_pp_select expects.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference.a3_segmenter import A3Segmenter  # noqa: E402
from inference.pipeline import MEAN, STD, default_device  # noqa: E402

CKPT = "models/checkpoints/phase2/seg_a3/unet_r18_fov1536{variant}_fold{k}_s17.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["a3tta"], default="a3tta")
    ap.add_argument("--variant", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    folds = json.loads((ROOT / "results/cache/segcv/folds.json").read_text())
    rows = data.load_split("idrid_seg_train")[0] + data.load_split("idrid_seg_val")[0]
    device = default_device()
    for k in range(5):
        seg = A3Segmenter(ROOT / CKPT.format(variant=args.variant, k=k), device, MEAN, STD, tta=True)
        for r in rows:
            if folds[r["image_id"]] != k or (out / f"{r['image_id']}.npz").exists():
                continue
            maps, box = seg.probs(data.load_image(r["image_filepath"]))
            np.savez_compressed(out / f"{r['image_id']}.npz", maps=(maps * 255).round().astype(np.uint8), box=np.array(box), fold=k)
        print(f"fold {k} done", flush=True)
    print(f"RESULT: out-of-fold flip-TTA maps for 50 IDRiD images in {args.out}", flush=True)


if __name__ == "__main__":
    main()
