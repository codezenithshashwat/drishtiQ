"""Fit and validate the photographic macular-edema risk rule against IDRiD 'risk of macular edema' labels.

Rule (same definition as the IDRiD labels): hard exudate within 1 disc diameter of the fovea -> high (label 2);
exudates elsewhere -> possible (label 1); none -> low (label 0). The only fitted parameter is the minimum exudate
region area (display px) that counts, chosen by macro-F1 on IDRiD dev-train; reported on IDRiD-val.
Uses the app's segmenter, post-processing and landmarks.
    .venv\\Scripts\\python -m eval.fit_dme [--name dme_rule_v2 --apply]
With --apply, configs/app/app.json "dme_rule" is pointed at the new file (the rule belongs to the app's segmenter).
"""
import argparse
import json

import numpy as np
from PIL import Image
from sklearn.metrics import confusion_matrix, f1_score

from . import ROOT, data, registry
from inference import findings, landmarks, postprocess as pp
from inference.pipeline import DISPLAY, Pipeline

AREAS = [0, 5, 10, 20, 40, 80, 160]


def exudate_regions(pipe, rows):
    out = []
    for r in rows:
        im = data.load_image(r["filepath"])
        scale = DISPLAY / max(im.size)
        size = (round(im.width * scale), round(im.height * scale))
        od = pp.locate_optic_disc(im)
        fv = landmarks.fovea(im, od)
        mask = pipe.segmenter.masks(im, size, od, lesions=["EX"])[0]["EX"][1]
        dd = 2 * od[2] * scale
        regs = [(r_["area_px"], float(np.hypot(r_["x"] - fv["x"] * scale, r_["y"] - fv["y"] * scale) / dd)) for r_ in findings.regions(mask)]
        out.append(dict(regions=regs, uncertain=fv["uncertain"]))
    return out


def predict(items, min_area):
    pred = []
    for it in items:
        ex = [d for a, d in it["regions"] if a >= min_area]
        pred.append(0 if not ex else 2 if min(ex) <= 1.0 else 1)
    return np.array(pred)


def summary(y, p):
    cm = confusion_matrix(y, p, labels=[0, 1, 2])
    return dict(n=int(len(y)), confusion_rows_true_cols_pred=cm.tolist(), macro_f1=float(f1_score(y, p, labels=[0, 1, 2], average="macro", zero_division=0)),
                high_risk_sensitivity=float(cm[2, 2] / max(cm[2].sum(), 1)), high_risk_ppv=float(cm[2, 2] / max(cm[:, 2].sum(), 1)),
                any_exudate_sensitivity=float(cm[1:, 1:].sum() / max(cm[1:].sum(), 1)), no_exudate_specificity=float(cm[0, 0] / max(cm[0].sum(), 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="dme_rule_v1")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    labels = {r["content_hash"]: int(r["DME_label"]) for r in data.read_csv(data.GRADING_TRAIN_MANIFEST)}
    pipe = Pipeline()
    sets = {}
    for name in ("idrid_grading_devtrain", "idrid_grading_val"):
        rows, _ = data.load_split(name)
        sets[name] = (np.array([labels[r["content_hash"]] for r in rows]), exudate_regions(pipe, rows))
    y_dev, dev = sets["idrid_grading_devtrain"]
    best = max(AREAS, key=lambda a: (f1_score(y_dev, predict(dev, a), labels=[0, 1, 2], average="macro", zero_division=0), -a))
    y_val, val = sets["idrid_grading_val"]
    p_val = predict(val, best)
    unc = np.array([it["uncertain"] for it in val])
    result = dict(min_exudate_area_px=best, fitted_on="IDRiD dev-train (macro-F1)", dev=summary(y_dev, predict(dev, best)),
                  val=summary(y_val, p_val), val_landmarks_uncertain=int(unc.sum()),
                  val_accuracy_landmarks_uncertain=float((p_val[unc] == y_val[unc]).mean()) if unc.any() else None,
                  val_accuracy_landmarks_confident=float((p_val[~unc] == y_val[~unc]).mean()))
    result["segmenter"] = {k: pipe.segmenter.spec[k] for k in ("EX",)}
    out = ROOT / f"configs/landmarks/{args.name}.json"
    out.write_text(json.dumps(result, indent=2))
    if args.apply:
        app_path = ROOT / "configs/app/app.json"
        app = json.loads(app_path.read_text())
        app["dme_rule"] = out.relative_to(ROOT).as_posix()
        app_path.write_text(json.dumps(app, indent=2) + "\n")
    v = result["val"]
    registry.record("dme-rule", args.name, dict(
        description="Photographic macular-edema risk rule (EX within 1 DD of fovea) on app segmenter + landmarks",
        train_data="min exudate area fitted on IDRiD dev-train", eval_overlap="no", eval_split="idrid_grading_val (DME labels)",
        n_images=v["n"], macro_f1=v["macro_f1"],
        notes=f"high-risk sensitivity {v['high_risk_sensitivity']:.3f}, PPV {v['high_risk_ppv']:.3f}; any-exudate sensitivity "
              f"{v['any_exudate_sensitivity']:.3f}; no-exudate specificity {v['no_exudate_specificity']:.3f}; confusion {v['confusion_rows_true_cols_pred']}"),
        result, dict(task="dme-rule", min_area_grid=AREAS))
    print(json.dumps(result, indent=2))
    print(f"RESULT: {args.name}: min exudate area {best} px; IDRiD-val high-risk sensitivity {v['high_risk_sensitivity']:.2f}, "
          f"PPV {v['high_risk_ppv']:.2f}, no-exudate specificity {v['no_exudate_specificity']:.2f}, macro-F1 {v['macro_f1']:.3f}"
          + ("; app rule switched" if args.apply else ""), flush=True)


if __name__ == "__main__":
    main()
