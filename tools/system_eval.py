"""Evaluate a candidate grading system (current app system + a patch) and apply its pre-registered rule (ADR-027..030).

    .venv\\Scripts\\python tools\\system_eval.py --name s1_thresholds --adr ADR-027 --rule s1 \\
        --patch '{"thresholds": "configs/grading/s1_thresholds.json"}' --apply

Rules (paired bootstrap, 2,000 resamples, candidate vs the current app system on IDRiD-val and APTOS-val):
  adr013  ADR-013 (ΔQWK CI > 0 on one set, lower bound > -0.05 on the other, severe under-grading not increased)
  s1      ADR-027 (Δmacro-F1 CI > 0 on one set, ΔQWK lower bound > -0.02 on both, severe not increased)
  g1/g4   ADR-028 (stage-1 / stage-4 recall gain CI > 0 on APTOS-val, ΔQWK lower bound > -0.02 on both, severe not increased)
"""
import argparse
import copy
import csv
import datetime as dt
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import compare, data, metrics, registry  # noqa: E402
from inference.finetuned import FinetunedGrader  # noqa: E402
from inference.pipeline import default_device  # noqa: E402
from inference.system import GradingSystem, system_name  # noqa: E402

APP_CONFIG = ROOT / "configs/app/app.json"
SPLITS = ("idrid_grading_val", "aptos_val")


def latest_run(model, split):
    rows = [r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8"))
            if r["task"] == "grade" and r["model"] == model and r["eval_split"] == split]
    return rows[-1]["run_id"] if rows else None


def evaluate(app, split):
    """Predictions of the system described by `app` on one split; registers a grading run under its system name."""
    device = default_device()
    grader = FinetunedGrader(sorted(glob.glob(str(ROOT / app["grader"].removeprefix("finetune:")))), device)
    system = GradingSystem(app, grader, device)
    rows, sha = data.load_split(split)
    y = np.array([int(r["DR_grade"]) for r in rows])
    preds = []
    for r in rows:
        im = data.load_image(r["filepath"])
        preds.append(system.stage(system.score(im), im))
    preds = np.array(preds)
    probs = np.eye(5)[preds]
    m = metrics.grading_metrics(y, probs)
    p, c = m["point"], m["ci95"]
    name = system.name
    row = dict(description=f"Grading system {json.dumps(app.get('system') or {}, sort_keys=True)} on {app['grader'].split('/')[-1]}",
               train_data="see components", eval_overlap="no", eval_split=split, n_images=m["n"], split_sha256=sha[:12],
               qwk=p["qwk"], qwk_ci=registry.ci(c["qwk"]), macro_f1=p["macro_f1"], macro_f1_ci=registry.ci(c["macro_f1"]),
               recall_g1_ci=registry.ci(c["recall_g1"]), severe_under=p["severe_under"], severe_under_ci=registry.ci(c["severe_under"]),
               referable_sens=p["referable_sens"], referable_spec=p["referable_spec"], notes=f"support {m['support']}",
               **{f"recall_g{k}": p[f"recall_g{k}"] for k in range(5)})
    run_id, folder = registry.record("grade", name, row, m, dict(task="grade", model=name, split=split, app=app))
    out = [dict(image=r.get("image_id") or r.get("id_code"), DR_grade=r["DR_grade"], predicted=int(k)) for r, k in zip(rows, preds)]
    data.write_csv(folder / f"predictions_{split}.csv", out, list(out[0]))
    print(f"{name} {split}: QWK {p['qwk']:.3f} macro-F1 {p['macro_f1']:.3f} recall g1 {p['recall_g1']:.2f} g4 {p['recall_g4']:.2f} ({run_id})", flush=True)
    return run_id


def rule(kind, d):
    lo = lambda s, k: d[s][k]["ci95"][0]
    severe_ok = all(lo(s, "severe_under") <= 0 for s in SPLITS)
    if kind == "adr013":
        ok = any(lo(s, "qwk") > 0 and all(lo(o, "qwk") > -0.05 for o in SPLITS if o != s) for s in SPLITS)
        return dict(qwk_rule=ok, severe_under_not_increased=severe_ok, passed=ok and severe_ok)
    qwk_ok = all(lo(s, "qwk") > -0.02 for s in SPLITS)
    if kind == "s1":
        gain = any(lo(s, "macro_f1") > 0 for s in SPLITS)
        return dict(macro_f1_gain_on_one=gain, qwk_lower_bound_above_minus_0_02=qwk_ok, severe_under_not_increased=severe_ok,
                    passed=gain and qwk_ok and severe_ok)
    key = {"g1": "recall_g1", "g4": "recall_g4"}[kind]
    gain = lo("aptos_val", key) > 0
    return dict(**{f"{key}_gain_ci_above_0_aptos": gain}, qwk_lower_bound_above_minus_0_02=qwk_ok, severe_under_not_increased=severe_ok,
                passed=gain and qwk_ok and severe_ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--adr", required=True)
    ap.add_argument("--rule", choices=["adr013", "s1", "g1", "g4"], required=True)
    ap.add_argument("--patch", default="{}", help="JSON merged into app.json 'system'")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--grader", help="replace the base grader (e.g. the CORN grader, ADR-029)")
    ap.add_argument("--drop", action="append", help="system part to remove in the candidate (e.g. thresholds)")
    args = ap.parse_args()
    app = json.loads(APP_CONFIG.read_text())
    if app.get("fusion"):
        print(f"RESULT: {args.adr} {args.name} not run: A4 fusion is active, and system candidates are evaluated without lesion "
              "features, so the comparison would not match the app. Recorded as skipped.", flush=True)
        (ROOT / f"queue/decisions/{args.name}.json").write_text(json.dumps(dict(name=args.name, adr=args.adr, skipped="fusion active"), indent=2))
        return
    cand = copy.deepcopy(app)
    if args.grader:  # S4: a different base grader (its own thresholds), other system parts kept unless dropped
        cand["grader"] = args.grader
    patch = json.loads(args.patch)
    sysc = {k: v for k, v in (cand.get("system") or {}).items() if k not in (args.drop or [])}
    for k, v in patch.items():
        sysc[k] = {**(sysc.get(k) or {}), **v} if isinstance(v, dict) else v
    cand["system"] = sysc
    base_name = system_name(app)
    base = {s: latest_run(base_name, s) or evaluate(app, s) for s in SPLITS}
    cand_runs = {s: evaluate(cand, s) for s in SPLITS}
    deltas = {s: compare.compare(base[s], cand_runs[s])["delta"] for s in SPLITS}
    verdict = rule(args.rule, deltas)
    switched = False
    if args.apply and verdict["passed"] and system_name(json.loads(APP_CONFIG.read_text())) == base_name:
        new = json.loads(APP_CONFIG.read_text())
        new.setdefault("history", []).append(dict(system=new.get("system"), version=new["version"], replaced=dt.datetime.now().isoformat(timespec="seconds"),
                                                  reason=f"{args.adr} ({args.name})"))
        new["system"] = sysc
        new["grader"] = cand["grader"]
        new["version"] = re.sub(r"^v0\.(\d+)", lambda m: f"v0.{int(m.group(1)) + 1}", new["version"].split(" ")[0]) + f" ({args.name})"
        APP_CONFIG.write_text(json.dumps(new, indent=2) + "\n")
        switched = True
    decision = dict(name=args.name, adr=args.adr, rule=args.rule, candidate=system_name(cand), baseline=base_name, patch=patch,
                    time=dt.datetime.now().isoformat(timespec="seconds"), verdict=verdict, app_grader_switched=switched,
                    splits={s: dict(baseline_run=base[s], candidate_run=cand_runs[s], delta=deltas[s]) for s in SPLITS})
    (ROOT / "queue/decisions").mkdir(parents=True, exist_ok=True)
    (ROOT / f"queue/decisions/{args.name}.json").write_text(json.dumps(decision, indent=2))
    q = "; ".join(f"{s.split('_')[0]} dQWK {d['qwk']['point']:+.3f} [{d['qwk']['ci95'][0]:+.3f}, {d['qwk']['ci95'][1]:+.3f}]" for s, d in deltas.items())
    print(f"RESULT: {args.adr} {args.name} {'PASS' if verdict['passed'] else 'FAIL'}; {q}; app system {'switched' if switched else 'unchanged'}", flush=True)


if __name__ == "__main__":
    main()
