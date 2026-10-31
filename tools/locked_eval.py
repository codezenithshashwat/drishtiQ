"""Step 7 (ADR-043): the ONE locked evaluation of rc-1 for grading + routing + quality. Runs once per set; never again.

    .venv\\Scripts\\python tools\\locked_eval.py idrid_test     # IDRiD clean test (102 images)
    .venv\\Scripts\\python tools\\locked_eval.py deepdrid       # DeepDRiD regular fundus (locked manifest, 500 patients)

Refuses to run unless HEAD is exactly the tag rc-1 with no tracked changes, and refuses if the set's result exists.
Every image goes through the app's own path: Pipeline.analyze -> assist.annotate (stage confidence, ADR-019) ->
routing.eye_state at the default 2.5% operating point -> routing.patient_state. Segmentation is NOT evaluated (the IDRiD
segmentation test stays locked). Writes results/locked/<set>.json and results/locked/<set>_images.jsonl, one registry row.
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta
from sklearn.metrics import cohen_kappa_score, f1_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results/locked"
TARGET = 0.025
B = 2000
SEED = 17


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def guard(name):
    tag = git("describe", "--tags", "--exact-match", "HEAD")
    if tag != "rc-1":
        raise SystemExit(f"locked evaluation runs only on the rc-1 tag (HEAD tag: {tag or 'none'})")
    changed = git("diff", "--name-only", "HEAD").splitlines()  # (porcelain parsing lost a character after strip; fixed after rc-1)
    # Outputs (registry, runs, locked results) may follow the tag; exploratory notebooks are not loaded by the app.
    if [c for c in changed if not c.startswith(("results/", "notebooks/"))]:
        raise SystemExit(f"tracked files differ from rc-1 outside results/ and notebooks/: {changed}; nothing may change after the tag")
    if changed:
        print(f"allowed tracked changes since rc-1 (not part of the system): {changed}", flush=True)
    if (OUT / f"{name}.json").exists():
        raise SystemExit(f"{name} was already evaluated once; locked sets are never re-run")


def cp_upper(k, n):
    return float(beta.ppf(0.975, k + 1, n - k)) if n and k < n else (1.0 if n else None)


def analyse(items, log_name):
    """items: dicts with path (+ ids). Returns per-image records from the app path; cached per image so an interrupted
    run resumes instead of re-running images (the set is still evaluated once)."""
    from inference import Pipeline, assist, routing
    OUT.mkdir(parents=True, exist_ok=True)
    pipe = Pipeline()
    cfg = json.loads((ROOT / "configs/app/app.json").read_text())
    cal = assist.load_calibration(cfg["grader"])
    valid = routing.routing_valid(pipe.grader_spec, pipe.checkpoints, pipe.system is not None, bool(pipe.fusion))  # as backend/app.py
    log = OUT / f"{log_name}_images.jsonl"
    done = {}
    if log.exists():
        for line in log.read_text().splitlines():
            r = json.loads(line)
            done[r["path"]] = r
    with log.open("a") as f:
        for n, it in enumerate(items):
            if it["path"] in done:
                continue
            a = pipe.analyze((ROOT / it["path"]).read_bytes())
            s = assist.annotate(a, cal) if a.get("status") == "ok" else {}
            st = routing.eye_state(a, eye=it.get("eye", "unknown"), target=TARGET, valid=valid, stage_confidence=s.get("stage_confidence"))
            ok = a.get("status") == "ok"
            rec = dict(path=it["path"], status=a.get("status"), usable=bool(ok and a["quality"]["usable"]),
                       stage=a["grading"]["grade"] if ok else None, score=a["grading"].get("score") if ok else None,
                       stage_confidence=s.get("stage_confidence"), dme=(a.get("findings") or {}).get("macular_edema_risk", {}).get("level") if ok else None,
                       state=st["state"], reasons=st["reasons"])
            f.write(json.dumps(rec) + "\n")
            f.flush()
            done[it["path"]] = rec
            if (n + 1) % 100 == 0:
                print(f"{log_name}: {n + 1}/{len(items)}", flush=True)
    return [done[it["path"]] for it in items], valid, cal


def grading_metrics(y, stage, p_ref):
    ref, pred_ref = y >= 2, stage >= 2
    out = dict(n=int(len(y)), qwk=float(cohen_kappa_score(y, stage, weights="quadratic")),
               macro_f1=float(f1_score(y, stage, labels=range(5), average="macro", zero_division=0)),
               within_one=float((np.abs(y - stage) <= 1).mean()),
               recall_per_grade={str(g): (float((stage[y == g] == g).mean()) if (y == g).any() else None) for g in range(5)},
               referable_sensitivity=float(pred_ref[ref].mean()) if ref.any() else None,
               referable_specificity=float((~pred_ref[~ref]).mean()) if (~ref).any() else None,
               referable_auroc=float(roc_auc_score(ref, p_ref)) if 0 < ref.sum() < len(ref) else None,
               decision_changing_errors=dict(referable_called_non_referable=int((ref & ~pred_ref).sum()),
                                             non_referable_called_referable=int((~ref & pred_ref).sum())))
    return out


def boot(units, fn, rng):
    """95% percentile CI of fn(resampled unit indices) over B resamples of the units."""
    vals = []
    for _ in range(B):
        v = fn(rng.integers(0, units, units))
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(v)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else None


def p_ref(score, cfg):
    return 1 / (1 + np.exp(-(cfg["platt"]["coef"] * score + cfg["platt"]["intercept"])))


def image_level(recs, y, rng, unit_of=None):
    """Grading on gradable images with a valid label, routing on all images; CIs by image or by unit (patient)."""
    from inference import routing
    cfg = routing.load_config()
    graded = np.array([r["stage"] is not None for r in recs]) & (y <= 4)
    st = np.array([r["stage"] if r["stage"] is not None else -1 for r in recs])
    sc = np.array([r["score"] if r["score"] is not None else 0.0 for r in recs])
    g = grading_metrics(y[graded], st[graded], p_ref(sc[graded], cfg))
    routine = np.array([r["state"] == routing.ROUTINE for r in recs])
    ref = (y >= 2) & (y <= 4)
    k, n_ref = int((routine & ref).sum()), int(ref.sum())
    deferred = np.array([r["stage_confidence"] is not None and r["stage_confidence"] < cfg["tau"] for r in recs])
    rt = dict(units="images", n=int(len(recs)), routed_routine=int(routine.sum()), coverage=float(routine.mean()), referable=n_ref,
              missed=k, miss_rate=k / n_ref if n_ref else None, miss_rate_upper95=cp_upper(k, n_ref),
              deferral_rate=float(deferred[graded].mean()), quality_flag_rate=float(np.mean([not r["usable"] for r in recs])))
    # bootstrap units: images, or patients (all images of a resampled patient)
    if unit_of is None:
        groups = [np.array([i]) for i in range(len(recs))]
    else:
        ids = sorted(set(unit_of))
        groups = [np.flatnonzero(np.array(unit_of) == u) for u in ids]

    def pick(ix):
        return np.concatenate([groups[i] for i in ix])

    def qwk(ix):
        j = pick(ix)
        j = j[graded[j]]
        return float(cohen_kappa_score(y[j], st[j], weights="quadratic")) if len(set(y[j])) > 1 else None

    def sens(ix):
        j = pick(ix)
        j = j[graded[j] & ref[j]]
        return float((st[j] >= 2).mean()) if len(j) else None

    def spec(ix):
        j = pick(ix)
        j = j[graded[j] & ~ref[j] & (y[j] <= 4)]
        return float((st[j] < 2).mean()) if len(j) else None

    def cov(ix):
        return float(routine[pick(ix)].mean())

    g["ci95"] = dict(qwk=boot(len(groups), qwk, rng), referable_sensitivity=boot(len(groups), sens, rng),
                     referable_specificity=boot(len(groups), spec, rng))
    rt["coverage_ci95"] = boot(len(groups), cov, rng)
    for grade in range(5):
        def rec_g(ix, grade=grade):
            j = pick(ix)
            j = j[graded[j] & (y[j] == grade)]
            return float((st[j] == grade).mean()) if len(j) else None
        g["ci95"][f"recall_{grade}"] = boot(len(groups), rec_g, rng)
    return g, rt


def idrid_test():
    guard("idrid_test")
    with open(ROOT / "data/interim/manifests/idrid_grading_test_clean.csv", newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["inclusion_status"] == "included"]
    items = [dict(path=r["filepath"]) for r in rows]
    recs, valid, _ = analyse(items, "idrid_test")
    y = np.array([int(r["DR_grade"]) for r in rows])
    g, rt = image_level(recs, y, np.random.default_rng(SEED))
    finish("idrid_test", "idrid_grading_test", dict(set="IDRiD clean test", n=len(rows), routing_valid=valid, grading=g, routing_images=rt,
                                                    note="Laterality is not recorded for IDRiD; the laterality check is skipped (eye unknown)."))


def deepdrid():
    from inference import routing
    guard("deepdrid")
    man = json.loads((ROOT / "data/interim/manifests/deepdrid_locked.json").read_text())
    imgs = man["images"]
    items = [dict(path=i["path"], eye="left" if "_l" in i["image_id"] else "right") for i in imgs]
    recs, valid, _ = analyse(items, "deepdrid")
    grade = lambda i: 5 if i["grade"] is None else int(i["grade"])  # noqa: E731  (None = DeepDRiD grade 5, "cannot be graded")
    y = np.array([grade(i) for i in imgs])
    pid = [i["patient_id"] for i in imgs]
    rng = np.random.default_rng(SEED)
    g, rt = image_level(recs, y, rng, unit_of=pid)

    # quality-gate agreement with DeepDRiD "Overall quality" (ADR-034a); grade 5 counts as poor
    good = np.array([bool(i["quality_ok"]) and grade(i) <= 4 for i in imgs])
    usable = np.array([r["usable"] for r in recs])
    quality = dict(accuracy=float((good == usable).mean()), flag_rate_among_poor=float((~usable[~good]).mean()) if (~good).any() else None,
                   flag_rate_among_good=float((~usable[good]).mean()), poor=int((~good).sum()), good=int(good.sum()))

    eye_grading, patient = eye_and_patient(imgs, recs, items, grade, rng)
    finish("deepdrid", "deepdrid_locked", dict(set="DeepDRiD regular fundus (locked)", n_images=len(imgs), n_patients=patient["n"], routing_valid=valid,
                                               primary_image_level=dict(grading=g, routing_images=rt), quality_gate=quality,
                                               secondary_eye_level_grading=eye_grading, patient_level_routing=patient,
                                               ci="bootstrap by patient (2,000 resamples)"))


def eye_and_patient(imgs, recs, items, grade, rng):
    """Eye level (ADR-035: max-score gradable view) and patient level (ADR-040 states; worse eye decides; ADR-043)."""
    from inference import routing
    cfg = routing.load_config()
    eyes = {}
    for i, r, it in zip(imgs, recs, items):
        eyes.setdefault((i["patient_id"], it["eye"]), []).append((i, r))
    eye_rows = {}
    for (p, side), views in eyes.items():
        gradable = [(i, r) for i, r in views if r["state"] != routing.RETAKE]
        label = grade(views[0][0])
        if not gradable:
            state, stage, score = routing.RETAKE, None, None
        else:
            state = max((r["state"] for _, r in gradable), key=lambda s: routing.SEVERITY[s])
            best = max(gradable, key=lambda v: v[1]["score"] if v[1]["score"] is not None else -9)
            score = best[1]["score"]
            stage = best[1]["stage"]
        eye_rows[(p, side)] = dict(patient=p, eye=side, state=state, stage=stage, score=score, label=label)
    patients = sorted({p for p, _ in eye_rows})
    pat = []
    for p in patients:
        es = [eye_rows[(p, s)] for s in ("right", "left") if (p, s) in eye_rows]
        ps = routing.patient_state([dict(eye=e["eye"], state=e["state"], stage=e["stage"], reasons=[]) for e in es])
        labels = [e["label"] for e in es if e["label"] <= 4]
        pat.append(dict(patient=p, state=ps["state"], referable=(max(labels) >= 2) if labels else None, eyes=len(es)))
    routine = np.array([q["state"] == routing.ROUTINE for q in pat])
    known = np.array([q["referable"] is not None for q in pat])
    refp = np.array([bool(q["referable"]) for q in pat])
    k, n_ref = int((routine & refp & known).sum()), int((refp & known).sum())
    states = {s: int(sum(q["state"] == s for q in pat)) for s in routing.SEVERITY}
    patient = dict(units="patients", n=len(pat), label_unknown=int((~known).sum()), routed_routine=int(routine.sum()),
                   coverage=float(routine.mean()), coverage_ci95=boot(len(pat), lambda ix: float(routine[ix].mean()), rng),
                   referable=n_ref, missed=k, miss_rate=k / n_ref if n_ref else None, miss_rate_upper95=cp_upper(k, n_ref), states=states,
                   referable_sensitivity_patient=float(np.mean([q["state"] != routing.ROUTINE for q in pat if q["referable"]])) if n_ref else None)
    # eye-level grading (secondary, ADR-035): max-score view, graded eyes with a label 0-4
    er = [e for e in eye_rows.values() if e["stage"] is not None and e["label"] <= 4]
    eye_grading = grading_metrics(np.array([e["label"] for e in er]), np.array([e["stage"] for e in er]),
                                  p_ref(np.array([e["score"] for e in er]), cfg))
    eye_grading["deferred_or_ungradable_eyes"] = int(sum(e["stage"] is None for e in eye_rows.values()))
    return eye_grading, patient


def finish(name, split, summary):
    from eval import registry
    summary.update(adr="ADR-043", tag="rc-1", commit=git("rev-parse", "HEAD"), operating_point=TARGET,
                   routing_config_sha256=hashlib.sha256((ROOT / "configs/routing/routing_v1.json").read_bytes()).hexdigest())
    (OUT / f"{name}.json").write_text(json.dumps(summary, indent=2))
    g = summary.get("grading") or summary["primary_image_level"]["grading"]
    rt = summary.get("patient_level_routing") or summary["routing_images"]
    registry.record("locked", f"rc-1:{name}", dict(description=f"ADR-043 locked evaluation of rc-1 ({summary['set']}); results/locked/{name}.json",
                    eval_overlap="no", eval_split=split, n_images=summary.get("n") or summary.get("n_images"), qwk=g["qwk"],
                    referable_sens=g["referable_sensitivity"], referable_spec=g["referable_specificity"],
                    notes=f"{rt['units']}: coverage {rt['coverage']:.4f}; miss {rt['missed']}/{rt['referable']} (upper95 {rt['miss_rate_upper95']})"),
                    summary, dict(task="locked", set=name))
    print(f"RESULT {name}: QWK {g['qwk']:.3f}; referable sens {g['referable_sensitivity']:.3f} spec {g['referable_specificity']:.3f}; "
          f"{rt['units']} coverage {rt['coverage']:.3f}, missed {rt['missed']}/{rt['referable']} (upper95 {rt['miss_rate_upper95']})", flush=True)


if __name__ == "__main__":
    {"idrid_test": idrid_test, "deepdrid": deepdrid}[sys.argv[1]]()
