"""Fit fovea-locator parameters on IDRiD dev-train localisation labels; evaluate disc and fovea on IDRiD-val.

Localisation images are matched to the frozen grading splits by file SHA-256; the localisation test set is never read.
    .venv\\Scripts\\python -m eval.fit_fovea
"""
import itertools
import json

import numpy as np

from . import ROOT, data, registry
from inference import postprocess as pp
from inference.landmarks import CONFIG, fovea_candidates, locate_fovea


def labelled():
    loc = {}
    for r in data.read_csv(ROOT / "outputs/metrics/idrid_localization_metadata.csv"):
        if r["split"] == "train":
            loc.setdefault(r["image_id"], {})[r["anatomy"].lower()] = (float(r["x"]), float(r["y"]))
    sha_to_id = {r["file_sha256"]: r["image_id"] for r in data.read_csv(data.GRADING_TRAIN_MANIFEST)}
    roles = {r["image_id"]: "dev" for r in data.load_split("idrid_grading_devtrain")[0]}
    roles.update({r["image_id"]: "val" for r in data.load_split("idrid_grading_val")[0]})
    out = {"dev": [], "val": []}
    for r in data.read_csv(ROOT / "results/audit/aptos/idrid_all_fingerprints.csv"):
        if "C. Localization" not in r["path"] or "Training Set" not in r["path"]:
            continue
        role = roles.get(sha_to_id.get(r["sha256"]))
        image_id = r["path"].rsplit("/", 1)[1].rsplit(".", 1)[0]
        if role and image_id in loc:
            out[role].append(dict(path=r["path"], od=loc[image_id]["od"], fovea=loc[image_id]["fovea"]))
    return out


def prepare(items):
    rows = []
    for it in items:
        im = data.load_image(it["path"])
        od = pp.locate_optic_disc(im)
        rows.append(dict(it, od_pred=od, cand=fovea_candidates(im, od), width=im.width))
    return rows


def evaluate(rows, params):
    od_err, fv_err, radius, uncertain = [], [], [], []
    for r in rows:
        x, y, _, unc = locate_fovea(r["cand"], params)
        rad = r["od_pred"][2]
        od_err.append(np.hypot(r["od_pred"][0] - r["od"][0], r["od_pred"][1] - r["od"][1]) / rad)
        fv_err.append(np.hypot(x - r["fovea"][0], y - r["fovea"][1]))
        radius.append(rad)
        uncertain.append(unc)
    fv_err, radius, uncertain = np.array(fv_err), np.array(radius), np.array(uncertain)
    within = fv_err <= radius
    return dict(n=len(rows), od_within_1_radius=float(np.mean(np.array(od_err) <= 1)),
                fovea_median_error_px=float(np.median(fv_err)), fovea_median_error_disc_radii=float(np.median(fv_err / radius)),
                fovea_within_1_disc_radius=float(within.mean()),
                flagged_uncertain=float(uncertain.mean()),
                fovea_within_1_disc_radius_when_confident=float(within[~uncertain].mean()) if (~uncertain).any() else None,
                fovea_within_1_disc_radius_when_flagged=float(within[uncertain].mean()) if uncertain.any() else None)


def main():
    sets = labelled()
    dev, val = prepare(sets["dev"]), prepare(sets["val"])
    grid = dict(distance_dd=[1.5, 1.75, 2.0, 2.25, 2.5], vertical_dd=[-0.15, 0.0, 0.15, 0.3], search_dd=[0.4, 0.5, 0.75, 1.0],
                min_contrast=[-np.inf])
    best = max((dict(zip(grid, v)) for v in itertools.product(*grid.values())),
               key=lambda p: (evaluate(dev, p)["fovea_within_1_disc_radius"], -evaluate(dev, p)["fovea_median_error_px"]))
    # Confidence: flag the 10% of dev-train images with the weakest macular contrast (fixed rule; its usefulness is
    # measured, not assumed: compare accuracy of flagged vs unflagged images).
    contrasts = np.array([locate_fovea(r["cand"], best)[2] for r in dev])
    best["min_contrast"] = float(np.percentile(contrasts, 10))
    result = dict(params=best, fitted_on=f"IDRiD dev-train localisation labels ({len(dev)} images)",
                  dev=evaluate(dev, best), val=evaluate(val, best))
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(result, indent=2))
    v = result["val"]
    registry.record("landmarks", "fovea_v1", dict(description="Optic disc (brightness heuristic) + fovea (prior + dark-spot search)",
                                                 train_data=result["fitted_on"], eval_overlap="no", eval_split="idrid_grading_val (localisation labels)",
                                                 n_images=v["n"],
                                                 notes=f"OD within 1 radius {v['od_within_1_disc_radius'] if 'od_within_1_disc_radius' in v else v['od_within_1_radius']:.3f}; "
                                                       f"fovea within 1 disc radius {v['fovea_within_1_disc_radius']:.3f}; median error {v['fovea_median_error_px']:.0f}px "
                                                       f"({v['fovea_median_error_disc_radii']:.2f} radii); flagged uncertain {v['flagged_uncertain']:.3f}"),
                    result, dict(task="landmarks", params=best))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
