"""ONE locked evaluation of release candidate rc-1 on an external / locked set (ADR-034).

    .venv\\Scripts\\python tools\\external_eval.py idrid_test
    .venv\\Scripts\\python tools\\external_eval.py deepdrid

Refuses to run unless the git tag rc-1 exists, the code checked out is exactly rc-1 (clean tree for tracked files),
and results/external/<set>.json does not exist yet (one run per set; nothing changes afterwards). The app pipeline is
used exactly as shipped (quality gate, grading system, calibration, deferral).

Reports: QWK, macro-F1, per-grade recall (bootstrap 95% CI), within-one-stage agreement, referable AUROC (calibrated
P(referable), or the grade score when uncalibrated) with sensitivity/specificity at the app operating point (stage >= 2),
decision-changing errors (referable <-> non-referable), deferral rate, and for DeepDRiD quality-gate agreement with
the dataset's quality labels.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import cohen_kappa_score, f1_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results/external"


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def guard(name):
    if not git("tag", "--list", "rc-1"):
        raise SystemExit("rc-1 is not tagged; external evaluation waits for the release candidate (ADR-034)")
    if git("rev-parse", "HEAD") != git("rev-list", "-n", "1", "rc-1"):
        raise SystemExit("HEAD is not rc-1; check out rc-1 before the locked evaluation")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("tracked files differ from rc-1; the locked evaluation needs the exact release candidate")
    if (OUT / f"{name}.json").exists():
        raise SystemExit(f"{name} was already evaluated once ({OUT / f'{name}.json'}); it is never re-run")


def items(name):
    if name == "idrid_test":
        rows = list(csv.DictReader(open(ROOT / "data/interim/manifests/idrid_grading_test_clean.csv", encoding="utf-8")))
        return [dict(id=r["image_id"], patient=r["image_id"], path=ROOT / r["filepath"], grade=int(r["DR_grade"]), quality=None) for r in rows
                if r.get("inclusion_status", "included") in ("included", "")]
    if name == "deepdrid":
        lock = json.loads((ROOT / "data/interim/manifests/deepdrid_locked.json").read_text())
        # grade None (no label) or 5 (ungradable) stay in for the quality-gate check but not in the grading metrics (ADR-034a)
        return [dict(id=r["image_id"], patient=r["patient_id"], path=ROOT / r["path"], grade=r["grade"], quality=r.get("quality_ok")) for r in lock["images"]]
    raise SystemExit(f"unknown set {name}")


def boot_ci(y, p, fn, groups, n=2000, seed=0):
    """Bootstrap CI resampling groups (patients for DeepDRiD, images for IDRiD), ADR-034a."""
    rng = np.random.default_rng(seed)
    ids = np.unique(groups)
    members = {g: np.nonzero(groups == g)[0] for g in ids}
    vals = []
    for _ in range(n):
        idx = np.concatenate([members[g] for g in rng.choice(ids, len(ids))])
        vals.append(fn(y[idx], p[idx]))
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def aggregate(recs):
    """ADR-035 secondary analyses for DeepDRiD. Eye: the usable image with the MAX score decides (its system stage and
    P(referable)); one image unusable -> the other; both unusable -> deferred. Patient: referable if the worse eye is."""
    eyes = {}
    for r in recs:
        pid, view = r["id"].split("_")
        eyes.setdefault((pid, view[0]), []).append(r)
    eye_rows, deferred = [], 0
    for (pid, eye), rs in eyes.items():
        grade = rs[0]["grade"]
        usable = [r for r in rs if r["status"] == "ok" and r["usable"] and r["stage"] is not None]
        if not usable:
            deferred += 1
            continue
        best = max(usable, key=lambda r: r["score"] if r["score"] is not None else -1)
        eye_rows.append(dict(patient=pid, eye=eye, grade=grade, stage=best["stage"], p_ref=best["p_ref"], score=best["score"]))
    graded = [e for e in eye_rows if e["grade"] is not None and int(e["grade"]) <= 4]
    y = np.array([int(e["grade"]) for e in graded])
    p = np.array([e["stage"] for e in graded])
    rank = np.array([e["p_ref"] if e["p_ref"] is not None else e["score"] for e in graded], float)
    groups = np.array([e["patient"] for e in graded])
    eye = dict(n_eyes=len(eyes), n_graded=len(graded), deferred_eyes=deferred,
               qwk=float(cohen_kappa_score(y, p, weights="quadratic")), qwk_ci95=boot_ci(y, p, lambda a, b: cohen_kappa_score(a, b, weights="quadratic"), groups),
               referable_auroc=float(roc_auc_score(y >= 2, rank)) if 0 < (y >= 2).sum() < len(y) else None,
               referable_sens=float((p[y >= 2] >= 2).mean()), referable_spec=float((p[y < 2] < 2).mean()), within_one=float((np.abs(y - p) <= 1).mean()))
    pats = {}
    for e in graded:
        t, s_ = pats.get(e["patient"], (False, False))
        pats[e["patient"]] = (t or int(e["grade"]) >= 2, s_ or e["stage"] >= 2)
    truth = np.array([v[0] for v in pats.values()])
    pred = np.array([v[1] for v in pats.values()])
    patient = dict(n_patients=len(pats), referable_sens=float(pred[truth].mean()) if truth.any() else None,
                   referable_spec=float((~pred[~truth]).mean()) if (~truth).any() else None)
    return dict(adr="ADR-035", eye_level=eye, patient_level=patient)


def main():
    name = sys.argv[1]
    guard(name)
    from backend.app import signature  # noqa: F401  (same import path as the server)
    from inference import Pipeline, assist
    pipe = Pipeline()
    cal = None if pipe.fusion or (pipe.system and pipe.system.changes_stage) else assist.load_calibration(pipe.system.name if pipe.system else pipe.grader_spec)
    recs = []
    for it in items(name):
        a = pipe.analyze(it["path"].read_bytes())
        s = assist.annotate(a, cal)
        ok = a.get("status") == "ok"
        recs.append(dict(id=it["id"], patient=it["patient"], grade=it["grade"], quality_label_ok=it["quality"], status=a.get("status"), usable=a["quality"]["usable"],
                         stage=a["grading"]["grade"] if ok else None, score=a["grading"].get("score") if ok else None,
                         p_ref=s.get("p_referable"), defer=bool(s.get("defer"))))
    graded = [r for r in recs if r["stage"] is not None and r["grade"] is not None and int(r["grade"]) <= 4]
    groups = np.array([str(r["patient"]) for r in graded])
    y = np.array([int(r["grade"]) for r in graded])
    p = np.array([r["stage"] for r in graded])
    ref_true = y >= 2
    rank = np.array([r["p_ref"] if r["p_ref"] is not None else r["score"] for r in graded], float)
    per_grade = {}
    for k in range(5):
        m = y == k
        if m.any():
            per_grade[k] = dict(n=int(m.sum()), recall=float((p[m] == k).mean()),
                                ci95=boot_ci(y, p, lambda a, b, k=k: float((b[a == k] == k).mean()) if (a == k).any() else np.nan, groups))
    out = dict(set=name, rc="rc-1", commit=git("rev-parse", "HEAD"), n_images=len(recs), n_graded=len(graded),
               excluded_ungradable_or_unlabelled=sum(1 for r in recs if r["grade"] is None or int(r["grade"]) > 4),
               rejected=sum(r["status"] != "ok" for r in recs), quality_flagged=sum(not r["usable"] for r in recs),
               qwk=float(cohen_kappa_score(y, p, weights="quadratic")),
               qwk_ci95=boot_ci(y, p, lambda a, b: cohen_kappa_score(a, b, weights="quadratic"), groups),
               macro_f1=float(f1_score(y, p, labels=range(5), average="macro", zero_division=0)),
               per_grade_recall=per_grade, within_one=float((np.abs(y - p) <= 1).mean()),
               referable_auroc=float(roc_auc_score(ref_true, rank)) if 0 < ref_true.sum() < len(y) else None,
               referable_sens=float((p[ref_true] >= 2).mean()), referable_spec=float((p[~ref_true] < 2).mean()),
               decision_changing_errors=dict(missed_referable=int(((p < 2) & ref_true).sum()), false_referral=int(((p >= 2) & ~ref_true).sum())),
               deferral_rate=float(np.mean([r["defer"] for r in recs])), calibrated=cal is not None)
    q = [r for r in recs if r["quality_label_ok"] is not None]
    if q:
        q = [r for r in q if r["grade"] != 5 or not r["quality_label_ok"]]
        out["quality_gate_agreement"] = dict(n=len(q), accuracy=float(np.mean([(r["usable"] and r["status"] == "ok") == bool(r["quality_label_ok"]) for r in q])),
                                             flagged_when_label_poor=float(np.mean([not r["usable"] for r in q if not r["quality_label_ok"]] or [np.nan])))
    if name == "deepdrid":
        out["secondary"] = aggregate(recs)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(dict(**out, per_image=recs), indent=2))
    print(f"RESULT: {name} (rc-1, n={len(recs)}): QWK {out['qwk']:.3f}, referable AUROC {out['referable_auroc']}, sens {out['referable_sens']:.3f}, "
          f"spec {out['referable_spec']:.3f}, deferral {out['deferral_rate']:.1%}", flush=True)


if __name__ == "__main__":
    main()
