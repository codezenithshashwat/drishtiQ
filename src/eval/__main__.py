"""CLI entry point: python -m eval {make-splits,grade,segment} (run with src on PYTHONPATH)."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from . import ROOT, data, metrics, models, registry
from inference import crop_back, postprocess as pp

DISPLAY = 1024  # resolution at which the app counts lesion regions


def cmd_make_splits(args):
    print(json.dumps(data.make_splits(), indent=2))
    for name in ["idrid_grading_devtrain", "idrid_grading_val", "idrid_seg_train", "idrid_seg_val"]:
        rows, _ = data.load_split(name)
        extra = f" grades={dict(sorted(Counter(int(r['DR_grade']) for r in rows).items()))}" if "DR_grade" in rows[0] else ""
        print(f"{name}: {len(rows)}{extra}")


def cmd_grade(args):
    split, split_sha = data.load_split(args.split)
    model, meta = models.grader(args.model)
    y = np.array([int(r["DR_grade"]) for r in split])
    start = time.perf_counter()
    probs = np.stack([model.probs(data.load_image(r["filepath"])) for r in split])
    seconds = (time.perf_counter() - start) / len(split)
    m = metrics.grading_metrics(y, probs, n_boot=args.bootstrap)
    p, c = m["point"], m["ci95"]
    row = dict(description=meta["description"], train_data=meta["train_data"], eval_overlap=meta["eval_overlap"],
               eval_split=args.split, n_images=m["n"], split_sha256=split_sha[:12],
               checkpoints_sha256=registry.checkpoints_hash(model.checkpoints),
               qwk=p["qwk"], qwk_ci=registry.ci(c["qwk"]), macro_f1=p["macro_f1"], macro_f1_ci=registry.ci(c["macro_f1"]),
               recall_g1_ci=registry.ci(c["recall_g1"]), severe_under=p["severe_under"], severe_under_ci=registry.ci(c["severe_under"]),
               referable_sens=p["referable_sens"], referable_spec=p["referable_spec"],
               notes=f"{seconds:.2f}s/img; support {m['support']}",
               **{f"recall_g{k}": p[f"recall_g{k}"] for k in range(5)})
    config = dict(task="grade", model=args.model, split=args.split, bootstrap=args.bootstrap, checkpoints=model.checkpoints)
    run_id, folder = registry.record("grade", args.model, row, {**m, "meta": meta, "seconds_per_image": seconds}, config)
    preds = [dict(image=r.get("image_id") or r.get("id_code"), DR_grade=r["DR_grade"], predicted=int(pr.argmax()),
                  **{f"p{k}": f"{pr[k]:.5f}" for k in range(5)}) for r, pr in zip(split, probs)]
    data.write_csv(folder / f"predictions_{args.split}.csv", preds, list(preds[0]))
    print(json.dumps(dict(run_id=run_id, **{k: row[k] for k in ["qwk", "qwk_ci", "macro_f1", "macro_f1_ci", "recall_g1", "recall_g1_ci",
                                                                 "severe_under", "severe_under_ci"]}), indent=2))
    print("confusion (rows=true, cols=pred):", m["confusion"])


def parse_thresholds(text):
    t = {l: 0.5 for l in data.LESIONS}
    for part in filter(None, (text or "").split(",")):
        k, v = part.split("=")
        t[k.strip().upper()] = float(v)
    return t


def cmd_segment(args):
    split, split_sha = data.load_split(args.split)
    model, meta = models.segmenter(args.model)
    params = json.loads((ROOT / args.postprocess).read_text()) if args.postprocess else None
    if params:
        params = {k: params[k] for k in pp.DEFAULT}
    thresholds = params["thresholds"] if params else parse_thresholds(args.thresholds)

    def lesion_mask(prob, lesion, im, od, fov):
        if not params:
            return prob, prob >= thresholds[lesion]
        masked = pp.masked_probs(prob, lesion, im, params, od=od, fov=fov)
        return masked, pp.binarize(masked, lesion, params, prob.shape[1])

    pr = {l: metrics.PixelPR() for l in data.LESIONS}
    counts = {l: [0, 0, 0] for l in data.LESIONS}  # tp, predicted, truth (pooled over images)
    per_image = []
    start = time.perf_counter()
    for r in split:
        im = data.load_image(r["image_filepath"])
        maps, box = model.probs(im)
        od = pp.locate_optic_disc(im) if params else None
        fov = pp.fov_mask(im, im.size, params["fov_erode_frac"]) if params else None
        rec = dict(image_id=r["image_id"])
        for i, lesion in enumerate(data.LESIONS):
            if not r[f"{lesion}_mask"]:
                continue  # missing mask = no supervision, never a negative
            truth = data.load_mask(r[f"{lesion}_mask"])
            prob = crop_back(maps[i], box, im.size)
            assert prob.shape == truth.shape, (r["image_id"], lesion, prob.shape, truth.shape)
            prob, pred = lesion_mask(prob, lesion, im, od, fov)
            pr[lesion].add(prob, truth)
            tp = int((pred & truth).sum())
            c = counts[lesion]
            c[0], c[1], c[2] = c[0] + tp, c[1] + int(pred.sum()), c[2] + int(truth.sum())
            rec[f"dice_{lesion}"] = round(2 * tp / max(int(pred.sum() + truth.sum()), 1), 5)
        per_image.append(rec)
    seconds = (time.perf_counter() - start) / len(split)

    # False-positive regions on grade-0 validation images (no DR => no lesions by definition), counted as the app does.
    grading, _ = data.load_split(args.grade0_split)
    g0 = [r for r in grading if r["DR_grade"] == "0"]
    fp_counts = {l: [] for l in data.LESIONS}
    for r in g0:
        im = data.load_image(r["filepath"])
        scale = DISPLAY / max(im.size)
        size = (round(im.width * scale), round(im.height * scale))
        if params:
            fov, od = pp.fov_mask(im, size, params["fov_erode_frac"]), pp.locate_optic_disc(im)
        else:
            fov, od = np.asarray(im.resize(size, Image.Resampling.BILINEAR).convert("L"), np.float32) > 15, None
        maps, box = model.probs(im)
        for i, lesion in enumerate(data.LESIONS):
            _, pred = lesion_mask(crop_back(maps[i], box, size), lesion, im, od, fov)
            fp_counts[lesion].append(metrics.count_regions(pred & fov))

    summary = {}
    for lesion in data.LESIONS:
        best_dice, best_t = pr[lesion].best_dice()
        tp, npred, ntruth = counts[lesion]
        summary[lesion] = dict(aupr=pr[lesion].aupr(), dice_pooled=2 * tp / max(npred + ntruth, 1),
                               precision=tp / max(npred, 1), recall=tp / max(ntruth, 1), threshold=thresholds[lesion],
                               images_with_mask=sum(1 for r in split if r[f"{lesion}_mask"]),
                               oracle_best_dice=best_dice, oracle_best_threshold=best_t,
                               fp_regions_grade0_mean=float(np.mean(fp_counts[lesion])),
                               fp_regions_grade0_median=float(np.median(fp_counts[lesion])))
    row = dict(description=meta["description"], train_data=meta["train_data"], eval_overlap=meta["eval_overlap"],
               eval_split=args.split, n_images=len(split), split_sha256=split_sha[:12],
               checkpoints_sha256=registry.checkpoints_hash(model.checkpoints),
               notes=f"{seconds:.2f}s/img; grade-0 FP images={len(g0)} from {args.grade0_split}; pooled pixel Dice; oracle-best Dice in metrics.json",
               **{f"aupr_{l}": summary[l]["aupr"] for l in data.LESIONS},
               **{f"dice_{l}": summary[l]["dice_pooled"] for l in data.LESIONS},
               **{f"threshold_{l}": thresholds[l] for l in data.LESIONS},
               **{f"fp_regions_g0_{l}": summary[l]["fp_regions_grade0_mean"] for l in data.LESIONS})
    config = dict(task="segment", model=args.model, split=args.split, thresholds=thresholds, grade0_split=args.grade0_split,
                  checkpoints=model.checkpoints, aupr_bins=metrics.BINS, postprocess=params, postprocess_file=args.postprocess)
    name = args.model + (f"+{Path(args.postprocess).stem}" if args.postprocess else "")
    run_id, folder = registry.record("segment", name, row, dict(per_lesion=summary, meta=meta, per_image=per_image), config)
    data.write_csv(folder / "per_image_dice.csv", per_image, ["image_id"] + [f"dice_{l}" for l in data.LESIONS])
    print(run_id)
    for lesion, s in summary.items():
        print(lesion, {k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()})


def cmd_agreement(args):
    """Exact and within-one-stage agreement plus referable sensitivity/specificity at the deployed operating point
    (AI stage >= 2), recomputed from an existing grading run's predictions file; no re-inference."""
    folder = registry.RESULTS / "runs" / args.run
    preds = data.read_csv(next(folder.glob("predictions_*.csv")))
    src = next(r for r in data.read_csv(registry.REGISTRY) if r["run_id"] == args.run)
    y = np.array([int(r["DR_grade"]) for r in preds])
    pred = np.array([int(r["predicted"]) for r in preds])
    point = metrics._point(y, pred)
    rng = np.random.default_rng(0)
    boot = {k: [] for k in ("accuracy", "within_one", "referable_sens", "referable_spec")}
    for _ in range(args.bootstrap):
        i = rng.integers(0, len(y), len(y))
        b = metrics._point(y[i], pred[i])
        for k in boot:
            boot[k].append(b[k])
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boot.items()}
    keep = {k: point[k] for k in boot}
    row = dict(description=f"Agreement summary of run {args.run}", train_data=src["train_data"], eval_overlap=src["eval_overlap"],
               eval_split=src["eval_split"], n_images=len(y), split_sha256=src["split_sha256"], referable_sens=point["referable_sens"],
               referable_spec=point["referable_spec"],
               notes=f"source run {args.run}; exact {point['accuracy']:.4f} {registry.ci(ci['accuracy'])}; "
                     f"within one stage {point['within_one']:.4f} {registry.ci(ci['within_one'])}; operating point: AI stage >= 2 is referable")
    run_id, _ = registry.record("agreement", src["model"], row, dict(source_run=args.run, point=keep, ci95=ci),
                                dict(task="agreement", source_run=args.run, bootstrap=args.bootstrap))
    print(json.dumps(dict(run_id=run_id, source_run=args.run, **{k: round(v, 4) for k, v in keep.items()}), indent=2))


def main():
    ap = argparse.ArgumentParser(prog="python -m eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("make-splits").set_defaults(fn=cmd_make_splits)
    g = sub.add_parser("grade")
    g.add_argument("--model", required=True)
    g.add_argument("--split", default="idrid_grading_val")
    g.add_argument("--bootstrap", type=int, default=2000)
    g.set_defaults(fn=cmd_grade)
    a = sub.add_parser("agreement")
    a.add_argument("--run", required=True, help="grading run id with a predictions file")
    a.add_argument("--bootstrap", type=int, default=2000)
    a.set_defaults(fn=cmd_agreement)
    s = sub.add_parser("segment")
    s.add_argument("--model", required=True)
    s.add_argument("--split", default="idrid_seg_val")
    s.add_argument("--grade0-split", default="idrid_grading_val")
    s.add_argument("--thresholds", help="e.g. MA=0.3,HE=0.5 (ignored when --postprocess is given)")
    s.add_argument("--postprocess", help="post-processing config, e.g. configs/postprocess/pp_v1.json")
    s.set_defaults(fn=cmd_segment)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
