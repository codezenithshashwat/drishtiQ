"""Paired bootstrap comparison of two grading runs on the same split (same images, same order).

    .venv\\Scripts\\python -m eval.compare <run_id_A> <run_id_B> [--n 2000]
Reports B - A for QWK, macro-F1 and severe under-grading with 95% CIs from resampling images jointly.
"""
import argparse
import json

import numpy as np

from . import data, metrics, registry


def load(run_id):
    folder = registry.RESULTS / "runs" / run_id
    files = list(folder.glob("predictions_*.csv"))
    if len(files) != 1:
        raise SystemExit(f"{run_id}: expected one predictions file, found {len(files)}")
    rows = data.read_csv(files[0])
    return files[0].stem.removeprefix("predictions_"), np.array([int(r["DR_grade"]) for r in rows]), np.array([int(r["predicted"]) for r in rows])


def compare(run_a, run_b, n=2000, seed=0):
    split_a, y, pa = load(run_a)
    split_b, yb, pb = load(run_b)
    assert split_a == split_b and np.array_equal(y, yb), "runs must be evaluated on the same split"
    rng = np.random.default_rng(seed)
    keys = ["qwk", "macro_f1", "severe_under", "recall_g1", "recall_g4"]
    point = {k: metrics._point(y, pb)[k] - metrics._point(y, pa)[k] for k in keys}
    boot = {k: [] for k in keys}
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        a, b = metrics._point(y[i], pa[i]), metrics._point(y[i], pb[i])
        for k in keys:
            boot[k].append(b[k] - a[k])
    return dict(split=split_a, n=len(y), a=run_a, b=run_b,
                delta={k: dict(point=point[k], ci95=[float(np.nanpercentile(boot[k], 2.5)), float(np.nanpercentile(boot[k], 97.5))]) for k in keys})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()
    print(json.dumps(compare(args.a, args.b, args.n), indent=2))


if __name__ == "__main__":
    main()
