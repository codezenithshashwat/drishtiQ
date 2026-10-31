"""B5 calibration + abstention (ADR-019) and B6 triage metrics (ADR-020) for the current app grader.

    .venv\\Scripts\\python tools\\assistant_metrics.py [--force]

Writes configs/calibration/app_grader.json, keyed by the grader spec. The app uses it only when the key matches the
app grader, so a grader swap makes the old calibration inactive until this job runs again (the queue runs it after
every job that can change the grader). Without --force it exits early when the file already matches the app grader.
"""
import argparse
import datetime as dt
import glob
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pseudo_label import FinetunedGrader, data, inner_holdout_scores, teacher_scores  # noqa: E402
from a4_fusion import inner_holdout_rows  # noqa: E402
from inference.system import GradingSystem, system_name  # noqa: E402

OUT = ROOT / "configs/calibration/app_grader.json"
TAUS = [round(0.50 + 0.05 * i, 2) for i in range(10)]
MIN_RETAINED_ACC = 0.85
VAL = ["idrid_grading_val", "aptos_val"]


def stage(scores, t):
    return np.searchsorted(np.asarray(t), scores, side="right")


def margin(scores, t):
    return np.min(np.abs(scores[:, None] - np.asarray(t)[None]), 1)


def ece(p, y, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any()))


def reliability(p, y, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [dict(bin=b, n=int((idx == b).sum()), mean_predicted=float(p[idx == b].mean()), observed=float(y[idx == b].mean()))
            for b in range(bins) if (idx == b).any()]


def triage(p_ref, defer, y):
    """ADR-020 worklist order: deferred first, then P(referable) descending."""
    order = np.lexsort((-p_ref, ~defer))
    ref = (y >= 2)[order]
    if ref.sum() == 0:
        return None
    reached = np.cumsum(ref) / ref.sum()
    top = max(1, int(round(0.2 * len(y))))
    return dict(auroc=float(roc_auc_score(y >= 2, p_ref)), referable_in_top20pct=float(ref[:top].sum() / ref.sum()),
                workload_to_95pct_sensitivity=float((np.argmax(reached >= 0.95) + 1) / len(y)), random_order_workload=0.95,
                n=int(len(y)), referable=int(ref.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    spec = system_name(app)  # the grading system (grader + thresholds / TTA), ADR-033
    if OUT.exists() and not args.force and json.loads(OUT.read_text()).get("grader") == spec:
        print(f"RESULT: calibration already matches app grader ({spec.split('/')[-1]}); nothing to do", flush=True)
        return
    if not spec.startswith("finetune:"):
        raise SystemExit("ADR-019 is defined for fine-tuned regression graders")
    grader = FinetunedGrader(sorted(glob.glob(str(ROOT / app["grader"].removeprefix("finetune:")))))
    system = GradingSystem(app, grader, grader.device)
    if system.changes_stage or app.get("fusion"):
        print("RESULT: calibration not applicable: specialists or fusion set the stage, not the calibrated score (ADR-033)", flush=True)
        return
    t = [float(x) for x in system.thresholds]

    if system.tta:  # TTA scores need the full images (the cached crops do not include the augmentations)
        rows_in = inner_holdout_rows()
        s_in = np.array([system.score(data.load_image(r["filepath"])) for _, r in rows_in])
        y_in = np.array([int(r["DR_grade"]) for _, r in rows_in])
    else:
        s_in, y_in, _ = inner_holdout_scores(grader)
    platt = LogisticRegression(C=1e6).fit(s_in[:, None], (y_in >= 2).astype(int))
    correct_in = (stage(s_in, t) == y_in).astype(float)
    iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(margin(s_in, t), correct_in)
    conf_in = iso.predict(margin(s_in, t))
    ok = [tau for tau in TAUS if (conf_in >= tau).any() and correct_in[conf_in >= tau].mean() >= MIN_RETAINED_ACC]
    tau = min(ok) if ok else 0.95

    report = {}
    for split in VAL:
        rows, _ = data.load_split(split)
        y = np.array([int(r["DR_grade"]) for r in rows])
        s = (np.array([system.score(data.load_image(r["filepath"])) for r in rows]) if system.tta
             else teacher_scores(grader, split, rows))
        pred, m = stage(s, t), margin(s, t)
        correct = (pred == y).astype(float)
        conf = iso.predict(m)
        p_ref = platt.predict_proba(s[:, None])[:, 1]
        raw_conf = np.clip(m / 0.5, 0, 1)
        defer = conf < tau
        keep = ~defer
        report[split] = dict(
            n=int(len(y)),
            ece_stage_confidence=dict(before=ece(raw_conf, correct), after=ece(conf, correct)),
            ece_p_referable=dict(before=ece((pred >= 2).astype(float), (y >= 2).astype(float)), after=ece(p_ref, (y >= 2).astype(float))),
            reliability_p_referable=reliability(p_ref, (y >= 2).astype(float)),
            abstention=dict(tau=tau, coverage=float(keep.mean()), accuracy_retained=float(correct[keep].mean()) if keep.any() else None,
                            accuracy_deferred=float(correct[defer].mean()) if defer.any() else None, accuracy_all=float(correct.mean()),
                            severe_under_retained=float((((y >= 3) & (pred <= 1)) & keep).sum() / max(((y >= 3) & keep).sum(), 1))),
            triage=triage(p_ref, defer, y))
    out = dict(grader=spec, created=dt.datetime.now().isoformat(timespec="seconds"), adr=["ADR-019", "ADR-020"],
               fitted_on=f"fine-tuner inner hold-out ({len(y_in)} images)", thresholds=t,
               platt=dict(coef=float(platt.coef_[0, 0]), intercept=float(platt.intercept_[0])),
               isotonic=dict(x=[float(v) for v in iso.X_thresholds_], y=[float(v) for v in iso.y_thresholds_]),
               tau=tau, tau_grid={str(x): float(correct_in[conf_in >= x].mean()) if (conf_in >= x).any() else None for x in TAUS},
               inner_holdout=dict(coverage=float((conf_in >= tau).mean()), accuracy_retained=float(correct_in[conf_in >= tau].mean())),
               validation=report)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    (ROOT / "queue/decisions").mkdir(parents=True, exist_ok=True)
    (ROOT / f"queue/decisions/assistant_metrics_{dt.datetime.now():%H%M}.json").write_text(json.dumps(out, indent=2))
    parts = [f"{k.split('_')[0]}: ECE P(ref) {v['ece_p_referable']['before']:.3f}->{v['ece_p_referable']['after']:.3f}, "
             f"coverage {v['abstention']['coverage']:.2f} acc retained {v['abstention']['accuracy_retained']:.3f} vs all {v['abstention']['accuracy_all']:.3f}, "
             f"AUROC {v['triage']['auroc']:.3f}, workload@95% {v['triage']['workload_to_95pct_sensitivity']:.2f}" for k, v in report.items()]
    print(f"RESULT: B5/B6 for {spec.split('/')[-1]}: tau {tau}; " + "; ".join(parts), flush=True)


if __name__ == "__main__":
    main()
