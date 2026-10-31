"""Fit the quality gate's corner-darkness threshold on training-side fundus images (ADR-023, R2 refit).

    .venv\\Scripts\\python tools\\fit_quality_gate.py

Fit set (training side only): 300 images each from IDRiD dev-train, APTOS-train and MMRDR-train (seed 17) and 64
synthetic non-fundus images (seed 99; R2 itself tests on seed 17). corner_dark_min is the smallest value on the grid
0.05..0.95 that flags every synthetic image; the share of training fundus images still passing is recorded. (A plain
percentile does not work: about 2% of MMRDR photos are cropped so the retina fills the frame.) Writes
configs/quality/quality_v1.json. No validation or test image is used.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference.pipeline import corner_dark  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from robustness import synthetic  # noqa: E402

OUT = ROOT / "configs/quality/quality_v1.json"


def main():
    rng = np.random.default_rng(17)
    values = {}
    for split in ("idrid_grading_devtrain", "aptos_train", "mmrdr_train"):
        rows, _ = data.load_split(split)
        vals = []
        for i in rng.choice(len(rows), min(300, len(rows)), replace=False):
            im = data.load_image(rows[i]["filepath"])
            small = np.asarray(im.resize((512, round(512 * im.height / im.width))), np.float32)
            vals.append(corner_dark(small.max(2) > 15))
        values[split] = vals
        print(split, "corner darkness percentiles 0.5/1/5:", np.percentile(vals, [0.5, 1, 5]).round(3), flush=True)
    syn = np.array([corner_dark(np.asarray(im.convert("RGB").resize((512, 384)), np.float32).max(2) > 15)
                    for _, im in synthetic(np.random.default_rng(99))])
    grid = [round(0.05 * k, 2) for k in range(1, 20)]
    threshold = next((t for t in grid if (syn < t).all()), grid[-1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(adr="ADR-023", corner_dark_min=threshold, fitted_on="300 images each from IDRiD dev-train, APTOS-train, MMRDR-train (seed 17) + 64 synthetic non-fundus images (seed 99)",
                                   training_pass_rate={k: float(np.mean(np.array(v) >= threshold)) for k, v in values.items()},
                                   synthetic_flagged=float((syn < threshold).mean())), indent=2))
    print(f"RESULT: corner_dark_min = {threshold}; training pass rate " +
          ", ".join(f"{k.split('_')[0]} {np.mean(np.array(v) >= threshold):.1%}" for k, v in values.items()), flush=True)


if __name__ == "__main__":
    main()
