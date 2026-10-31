"""Choose segmentation post-processing on 5-fold out-of-fold (OOF) maps of the 50 IDRiD dev segmentation images.

    .venv\\Scripts\\python -m eval.seg_pp_select --out configs/postprocess/pp_v1.json

Per lesion, maximises pooled pixel Dice over: FOV erosion, optic-disc masking radius (MA, EX), threshold and
component area limits. Writes the chosen parameters and records two registry rows (OOF without and with the
chosen post-processing). The frozen 10-image validation split is fold 4 of this CV, so settings chosen here are
not independent of that split; the CV estimate is the primary evidence.
"""
import argparse
import itertools
import json
import time

import numpy as np
from scipy import ndimage as ndi

from . import ROOT, data, metrics, registry
from inference import crop_back, postprocess as pp

CACHE = ROOT / "results/cache/segcv"
FOV_ERODE = [0.0, 0.01]
OD = {"MA": [None, 1.0, 1.5], "EX": [None, 1.0, 1.5], "HE": [None], "SE": [None]}
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]
MIN_AREA = {"MA": [0, 5, 10, 20, 40], "HE": [0, 20, 50], "EX": [0, 10, 30], "SE": [0, 50, 200]}
MAX_AREA = {"MA": [None, 2000], "HE": [None], "EX": [None], "SE": [None]}


def v0_fold4_probs():
    """probs(im) of the v0-recipe fold-4 CV models (trained on the 40 seg dev-train images; never saw grading images)."""
    import torch
    import segmentation_models_pytorch as smp
    from inference import default_device, letterbox, to_tensor
    device = default_device()
    ckpt = ROOT / "models/checkpoints/phase1/segcv"
    seg4 = smp.Segformer(encoder_name="mit_b0", encoder_weights=None, classes=4, decoder_segmentation_channels=128)
    seg4.load_state_dict(torch.load(ckpt / "segformer_fold4_s17.pt", map_location="cpu", weights_only=True))
    ma = smp.Unet(encoder_name="resnet18", encoder_weights=None, classes=1, decoder_channels=(128, 64, 32, 16, 16))
    ma.load_state_dict(torch.load(ckpt / "ma_unet_fold4_s17.pt", map_location="cpu", weights_only=True))
    seg4, ma = seg4.to(device).eval(), ma.to(device).eval()

    def probs(im):
        x512, box = letterbox(im, 512)
        with torch.no_grad():
            x = to_tensor(x512, device)
            maps = seg4(x).sigmoid()[0].cpu().numpy()
            maps[0] = ma(x).sigmoid()[0, 0].cpu().numpy()
        return maps, box
    return probs


def grade0_false_positives(keys, probs, display=1024):
    """Mean lesion regions per grade-0 dev-train grading image (no DR => every region is false), for each candidate
    setting, using a fold-4 model (never trained on grading images)."""
    rows = [r for r in data.load_split("idrid_grading_devtrain")[0] if r["DR_grade"] == "0"]
    total = {k: 0 for k in keys}
    for r in rows:
        im = data.load_image(r["filepath"])
        scale = display / max(im.size)
        size = (round(im.width * scale), round(im.height * scale))
        maps, box = probs(im)
        od = pp.locate_optic_disc(im)
        fovs = {e: pp.fov_mask(im, size, e) for e in FOV_ERODE}
        for i, lesion in enumerate(data.LESIONS):
            prob = crop_back(maps[i], box, size)
            for e, odf in itertools.product(FOV_ERODE, OD[lesion]):
                params = {"fov_erode_frac": e, "od_mask_lesions": [lesion] if odf else [], "od_radius_factor": odf or 1.0}
                masked = pp.masked_probs(prob, lesion, im, params, od=od, fov=fovs[e])
                for t in THRESHOLDS:
                    labels, k = ndi.label(masked >= t, np.ones((3, 3)))
                    area = np.bincount(labels.ravel(), minlength=k + 1)[1:] / (size[0] / pp.REF_WIDTH) ** 2
                    for lo, hi in itertools.product(MIN_AREA[lesion], MAX_AREA[lesion]):
                        keep = area >= lo
                        if hi is not None:
                            keep &= area <= hi
                        total[(lesion, e, odf, t, lo, hi)] += int(keep.sum())
    return {k: v / len(rows) for k, v in total.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="configs/postprocess/pp_v1.json")
    ap.add_argument("--cache", default="results/cache/segcv", help="folder of OOF maps (<image_id>.npz) and folds")
    ap.add_argument("--fold4-model", default="v0-recipe", help="'v0-recipe' or a segmenter spec such as a3:<checkpoint>")
    ap.add_argument("--label", default="v0-recipe-cv", help="registry model name prefix")
    ap.add_argument("--fp-constraint", action="store_true",
                    help="only accept settings that do not increase false-positive regions on grade-0 dev-train images")
    args = ap.parse_args()
    rows = data.load_split("idrid_seg_train")[0] + data.load_split("idrid_seg_val")[0]
    cache = ROOT / args.cache
    fold_of = json.loads((CACHE / "folds.json").read_text())  # the same 5-fold assignment for every recipe
    # stats[(lesion, erode, od, thr, lo, hi)] = [tp, pred, truth]
    stats = {}
    pr = {}  # (lesion, erode, od) -> PixelPR
    start = time.perf_counter()
    for n, r in enumerate(rows):
        im = data.load_image(r["image_filepath"])
        cached = np.load(cache / f"{r['image_id']}.npz")
        maps, box = cached["maps"].astype(np.float32) / 255, tuple(cached["box"])
        od = pp.locate_optic_disc(im)
        fovs = {e: pp.fov_mask(im, im.size, e) for e in FOV_ERODE}
        for i, lesion in enumerate(data.LESIONS):
            if not r[f"{lesion}_mask"]:
                continue
            truth = data.load_mask(r[f"{lesion}_mask"])
            prob = crop_back(maps[i], box, im.size)
            n_truth = int(truth.sum())
            for e, odf in itertools.product(FOV_ERODE, OD[lesion]):
                params = {"fov_erode_frac": e, "od_mask_lesions": [lesion] if odf else [], "od_radius_factor": odf or 1.0}
                masked = pp.masked_probs(prob, lesion, im, params, od=od, fov=fovs[e])
                pr.setdefault((lesion, e, odf), metrics.PixelPR()).add(masked, truth)
                for t in THRESHOLDS:
                    labels, k = ndi.label(masked >= t, np.ones((3, 3)))
                    area = np.bincount(labels.ravel(), minlength=k + 1)[1:]
                    overlap = np.bincount(labels.ravel(), weights=truth.ravel(), minlength=k + 1)[1:]
                    for lo, hi in itertools.product(MIN_AREA[lesion], MAX_AREA[lesion]):
                        keep = area >= lo
                        if hi is not None:
                            keep &= area <= hi
                        s = stats.setdefault((lesion, e, odf, t, lo, hi), [0, 0, 0])
                        s[0] += float(overlap[keep].sum())
                        s[1] += float(area[keep].sum())
                        s[2] += n_truth
        print(f"{n + 1}/{len(rows)} {r['image_id']} ({time.perf_counter() - start:.0f}s)", flush=True)

    dice = {k: 2 * v[0] / max(v[1] + v[2], 1) for k, v in stats.items()}
    precision = {k: v[0] / max(v[1], 1) for k, v in stats.items()}
    recall = {k: v[0] / max(v[2], 1) for k, v in stats.items()}
    baseline = {l: (l, 0.0, None, 0.5, 0, None) for l in data.LESIONS}
    if args.fp_constraint:
        from . import models
        probs = v0_fold4_probs() if args.fold4_model == "v0-recipe" else models.segmenter(args.fold4_model)[0].probs
        fp = grade0_false_positives(list(stats), probs)
    else:
        fp = None

    # FOV erosion is shared across lesions: pick the value maximising mean best-Dice.
    def best_for(lesion, e):
        cands = [k for k in dice if k[0] == lesion and k[1] == e]
        if fp is not None:  # never accept more false-positive regions on grade-0 images than no post-processing
            cands = [k for k in cands if fp[k] <= fp[baseline[lesion]]] or [baseline[lesion]]
        return max(cands, key=lambda k: (round(dice[k], 4), -(k[2] or 0), -k[4]))  # ties: prefer less masking/filtering
    erode = max(FOV_ERODE, key=lambda e: np.mean([dice[best_for(l, e)] for l in data.LESIONS]))
    chosen = {l: best_for(l, erode) for l in data.LESIONS}

    params = {"fov_erode_frac": erode,
              "od_mask_lesions": [l for l in data.LESIONS if chosen[l][2]],
              "od_radius_factor": max([chosen[l][2] for l in data.LESIONS if chosen[l][2]] or [1.0]),
              "thresholds": {l: chosen[l][3] for l in data.LESIONS},
              "min_area": {l: chosen[l][4] for l in data.LESIONS},
              "max_area": {l: chosen[l][5] for l in data.LESIONS}}
    if len({chosen[l][2] for l in params["od_mask_lesions"]}) > 1:
        print("note: MA and EX preferred different disc radii; using the larger for both")
    summary = {l: dict(baseline=dict(dice=dice[baseline[l]], precision=precision[baseline[l]], recall=recall[baseline[l]],
                                     aupr=pr[(l, 0.0, None)].aupr(), fp_regions_g0_dev=fp[baseline[l]] if fp else None),
                       chosen=dict(key=list(chosen[l]), dice=dice[chosen[l]], precision=precision[chosen[l]], recall=recall[chosen[l]],
                                   aupr=pr[(l, erode, chosen[l][2])].aupr(), fp_regions_g0_dev=fp[chosen[l]] if fp else None))
               for l in data.LESIONS}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    selected_on = "5-fold OOF, 50 IDRiD dev segmentation images, pooled pixel Dice"
    if fp:
        selected_on += "; constraint: grade-0 FP regions (fold-4 model, 100 grade-0 dev-train grading images) <= no post-processing"
    out.write_text(json.dumps({**params, "selected_on": selected_on,
                               "oof_summary": summary}, indent=2))
    split_sha = data.file_sha(CACHE / "folds.json")[:12]
    for label, key in (("no post-processing", "baseline"), (f"post-processing {out.stem}", "chosen")):
        row = dict(description=f"{args.label}: 5-fold CV OOF ({label})", train_data=f"{args.label} recipe; each IDRiD map from a model that did not train on that image",
                   eval_overlap="no (out-of-fold); settings selected on these same OOF maps" if key == "chosen" else "no (out-of-fold)",
                   eval_split="idrid_seg_cv50_oof", n_images=len(rows), split_sha256=split_sha,
                   notes="pooled pixel Dice; FP regions on grade-0 not applicable to CV fold models",
                   **{f"aupr_{l}": summary[l][key]["aupr"] for l in data.LESIONS},
                   **{f"dice_{l}": summary[l][key]["dice"] for l in data.LESIONS},
                   **{f"threshold_{l}": (0.5 if key == "baseline" else params["thresholds"][l]) for l in data.LESIONS})
        registry.record("segment", f"{args.label}{'' if key == 'baseline' else '+' + out.stem}", row, dict(summary=summary, params=params),
                        dict(task="segment-cv", postprocess=params if key == "chosen" else None, grid=dict(
                            fov=FOV_ERODE, od=OD, thresholds=THRESHOLDS, min_area=MIN_AREA, max_area=MAX_AREA)))
    print(json.dumps(params, indent=2))
    for l in data.LESIONS:
        print(l, {k: {m: round(v, 4) for m, v in s.items() if m != "key"} for k, s in summary[l].items()}, "chosen", summary[l]["chosen"]["key"])


if __name__ == "__main__":
    main()
