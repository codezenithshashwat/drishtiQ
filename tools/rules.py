"""Mechanical application of pre-registered swap rules (ADR-013/015/017). Used by the GPU queue; no judgement calls.

    .venv\\Scripts\\python tools\\rules.py grader-swap --name a2_swap --adr ADR-013 \\
        --candidate "finetune:models/.../x_s17.pt" \\
        --baseline idrid_grading_val=<run> --baseline aptos_val=<run> \\
        [--candidate-run idrid_grading_val=<run> ...] [--apply]

Evaluates the candidate (unless runs are given), runs the paired bootstrap against each baseline run, applies the
three-condition rule, writes queue/decisions/<name>.json and, with --apply and a pass, switches configs/app/app.json.
The previous grader is kept in the config's "history" list, so a swap is reversible by editing one line.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import compare  # noqa: E402

PY = str(ROOT / ".venv/Scripts/python.exe")
APP_CONFIG = ROOT / "configs/app/app.json"
DECISIONS = ROOT / "queue/decisions"


def pairs(items):
    return dict(i.split("=", 1) for i in items or [])


def evaluate(spec, split):
    """Run the harness on one split and return the new registry run id."""
    out = subprocess.run([PY, "-m", "eval", "grade", "--model", spec, "--split", split], cwd=ROOT, capture_output=True,
                         text=True, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    print(out.stdout[-2000:], out.stderr[-2000:], flush=True)
    if out.returncode:
        raise SystemExit(f"evaluation of {spec} on {split} failed")
    return re.search(r'"run_id": "([^"]+)"', out.stdout).group(1)


def run_metrics(run_id):
    m = json.loads((ROOT / "results/runs" / run_id / "metrics.json").read_text())
    return {**m["point"], "confusion": m.get("confusion"), "seconds_per_image": m.get("seconds_per_image")}


def grader_rule(deltas):
    """ADR-013 conditions on {split: compare() delta dict}."""
    lo = {s: d["qwk"]["ci95"][0] for s, d in deltas.items()}
    splits = list(lo)
    c1_c2 = any(lo[s] > 0 and all(lo[o] > -0.05 for o in splits if o != s) for s in splits)
    c3 = all(d["severe_under"]["ci95"][0] <= 0 for d in deltas.values())
    return dict(qwk_ci_above_0_on_one_and_lower_bound_above_minus_0_05_on_other=c1_c2,
                severe_under_not_significantly_increased=c3, passed=bool(c1_c2 and c3))


def switch_app_grader(spec, reason):
    app = json.loads(APP_CONFIG.read_text())
    if app["grader"] == spec:
        return False
    app.setdefault("history", []).append(dict(grader=app["grader"], version=app["version"], replaced=dt.datetime.now().isoformat(timespec="seconds"),
                                             reason=reason))
    app["grader"] = spec
    app["version"] = re.sub(r"^v0\.(\d+)", lambda m: f"v0.{int(m.group(1)) + 1}", app["version"].split(" ")[0]) + f" (grader {spec.split('/')[-1]})"
    app["grader_note"] = f"Swapped in by {reason}. Previous graders are listed under history; revert by restoring one."
    APP_CONFIG.write_text(json.dumps(app, indent=2) + "\n")
    return True


def app_grader_runs(splits=("idrid_grading_val", "aptos_val")):
    """Latest registry grading runs of the current app grader (evaluated now if it has none)."""
    import csv
    spec = json.loads(APP_CONFIG.read_text())["grader"]
    rows = list(csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8")))
    out = {}
    for split in splits:
        hits = [r["run_id"] for r in rows if r["task"] == "grade" and r["model"] == spec and r["eval_split"] == split]
        out[split] = hits[-1] if hits else evaluate(spec, split)
    return spec, out


def set_app_key(key, value, reason):
    app = json.loads(APP_CONFIG.read_text())
    if app.get(key) == value:
        return False
    app.setdefault("history", []).append({key: app.get(key), "version": app["version"], "replaced": dt.datetime.now().isoformat(timespec="seconds"), "reason": reason})
    app[key] = value
    app["version"] = re.sub(r"^v0\.(\d+)", lambda m: f"v0.{int(m.group(1)) + 1}", app["version"].split(" ")[0]) + f" ({key} {Path(value).stem})"
    APP_CONFIG.write_text(json.dumps(app, indent=2) + "\n")
    return True


def cmd_grader_swap(args):
    base, cand = pairs(args.baseline), pairs(args.candidate_run)
    app_spec = None
    if args.baseline_app:
        app_spec, base = app_grader_runs()
    if args.candidate_latest:  # candidate runs registered by an earlier step under the candidate's model name
        import csv
        rows = list(csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8")))
        for split in base:
            hits = [r["run_id"] for r in rows if r["task"] == "grade" and r["model"] == args.candidate and r["eval_split"] == split]
            if hits:
                cand[split] = hits[-1]
    for split in base:
        if split not in cand:
            cand[split] = evaluate(args.candidate, split)
    deltas, per_split = {}, {}
    for split, b in base.items():
        r = compare.compare(b, cand[split])
        deltas[split] = r["delta"]
        mb, mc = run_metrics(b), run_metrics(cand[split])
        per_split[split] = dict(baseline_run=b, candidate_run=cand[split], delta=r["delta"],
                                baseline=dict(qwk=mb.get("qwk"), severe_under=mb.get("severe_under"), seconds_per_image=mb.get("seconds_per_image")),
                                candidate=dict(qwk=mc.get("qwk"), macro_f1=mc.get("macro_f1"), recall_g1=mc.get("recall_g1"),
                                               severe_under=mc.get("severe_under"), seconds_per_image=mc.get("seconds_per_image"),
                                               confusion=mc.get("confusion")))
    verdict = grader_rule(deltas)
    if args.require_recall_g1_gain:  # ADR-021: stage-1 recall on this split must improve (CI above 0)
        lo = deltas[args.require_recall_g1_gain]["recall_g1"]["ci95"][0]
        verdict["recall_g1_gain_ci_above_0"] = bool(lo > 0)
        verdict["passed"] = bool(verdict["passed"] and lo > 0)
    if app_spec:
        verdict["comparator"] = f"app grader at decision time: {app_spec}"
    current = json.loads(APP_CONFIG.read_text())["grader"]
    may_apply = args.apply and (not args.require_app_grader or current == args.require_app_grader)
    if args.apply and not may_apply:
        verdict["apply_skipped"] = f"app grader is {current}, not {args.require_app_grader}; the rule's comparator is not the app grader"
    if args.apply_as == "fusion":
        swapped = bool(may_apply and verdict["passed"] and set_app_key("fusion", args.candidate.removeprefix("fusion:"), f"{args.adr} ({args.name})"))
    else:
        swapped = bool(may_apply and verdict["passed"] and switch_app_grader(args.candidate, f"{args.adr} ({args.name})"))
    decision = dict(name=args.name, adr=args.adr, candidate=args.candidate, time=dt.datetime.now().isoformat(timespec="seconds"),
                    verdict=verdict, app_grader_switched=swapped, splits=per_split)
    DECISIONS.mkdir(parents=True, exist_ok=True)
    (DECISIONS / f"{args.name}.json").write_text(json.dumps(decision, indent=2))
    q = ", ".join(f"{s.split('_')[0]} dQWK {d['qwk']['point']:+.3f} [{d['qwk']['ci95'][0]:+.3f}, {d['qwk']['ci95'][1]:+.3f}]" for s, d in deltas.items())
    print(f"RESULT: {args.adr} {'PASS' if verdict['passed'] else 'FAIL'}; {q}; app grader {'switched' if swapped else 'unchanged'}", flush=True)


LESIONS = ["MA", "HE", "EX", "SE"]


def latest_row(model, split):
    import csv
    rows = [r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8"))
            if r["task"] == "segment" and r["model"] == model and r["eval_split"] == split]
    if not rows:
        raise SystemExit(f"no registry row for {model} on {split}")
    return rows[-1]


def app_seg_entry(app, lesion, base_pp):
    """The app's current segmenter for one lesion: (model spec, post-processing file, CV registry label)."""
    e = (app.get("segmenter") or {}).get(lesion) or dict(model="v0", postprocess=base_pp, cv="v0-recipe-cv")
    return e["model"], e["postprocess"], e.get("cv", "v0-recipe-cv")


def cmd_seg_swap(args):
    """ADR-016, per lesion, post-processed rows. With --base-from-app each lesion is compared with the segmenter the app
    uses for it now (later candidates, ADR-031); otherwise with v0.1 (v0 + pp_v2). Output keys 'v0_1'/'a3' mean
    baseline/candidate."""
    app = json.loads(APP_CONFIG.read_text())
    lesions = args.lesions.split(",") if args.lesions else LESIONS
    f = lambda r, col: float(r[col]) if r[col] not in ("", "nan") else float("nan")
    per, runs = {}, {}
    for l in lesions:
        if args.base_from_app:
            model, pp_file, cv = app_seg_entry(app, l, args.base_pp)
            base_name, base_cv = f"{model}+{Path(pp_file).stem}", f"{cv}+{Path(pp_file).stem}"
        else:
            base_name, base_cv = args.base, args.base_cv
        rows = {k: (latest_row(b, split), latest_row(n, split)) for k, (b, n, split) in dict(
            cv=(base_cv, args.new_cv, "idrid_seg_cv50_oof"), ddr=(base_name, args.new, "ddr_seg_test"),
            val=(base_name, args.new, "idrid_seg_val")).items()}
        a = {k: (f(b, f"aupr_{l}"), f(n, f"aupr_{l}")) for k, (b, n) in rows.items()}
        fp = (f(rows["val"][0], f"fp_regions_g0_{l}"), f(rows["val"][1], f"fp_regions_g0_{l}"))
        checks = dict(cv_aupr_improves=a["cv"][1] > a["cv"][0], ddr_test_aupr_improves=a["ddr"][1] > a["ddr"][0],
                      idrid_val_aupr_drop_at_most_0_05=a["val"][1] >= a["val"][0] - 0.05, grade0_fp_not_increased=fp[1] <= fp[0])
        per[l] = dict(baseline=base_name, aupr={k: dict(v0_1=v[0], a3=v[1]) for k, v in a.items()}, fp_regions_g0=dict(v0_1=fp[0], a3=fp[1]),
                      checks=checks, passed=all(checks.values()))
        runs[l] = {k: dict(v0_1=b["run_id"], a3=n["run_id"]) for k, (b, n) in rows.items()}
    swap = [l for l in lesions if per[l]["passed"]]
    switched = False
    if args.apply and swap:
        seg = app.get("segmenter") or {l: dict(model="v0", postprocess=args.base_pp, cv="v0-recipe-cv") for l in LESIONS}
        new = {**seg, **{l: dict(model=args.new_spec, postprocess=args.new_pp, cv=args.new_cv.split("+")[0]) for l in swap}}
        if new != seg:
            app.setdefault("history", []).append(dict(segmenter=seg, replaced=dt.datetime.now().isoformat(timespec="seconds"),
                                                     reason=f"ADR-016 ({args.name}): lesions {swap}"))
            app["segmenter"] = new
            app["version"] = re.sub(r"^v0\.(\d+)", lambda m: f"v0.{int(m.group(1)) + 1}", app["version"].split(" ")[0]) + f" ({args.name}: {'/'.join(swap)})"
            APP_CONFIG.write_text(json.dumps(app, indent=2) + "\n")
            switched = True
    decision = dict(name=args.name, adr=args.adr, time=dt.datetime.now().isoformat(timespec="seconds"), per_lesion=per,
                    lesions_swapped=swap if switched else [], runs=runs)
    DECISIONS.mkdir(parents=True, exist_ok=True)
    (DECISIONS / f"{args.name}.json").write_text(json.dumps(decision, indent=2))
    print(f"RESULT: {args.adr} {args.name} " + "; ".join(f"{l} {'PASS' if per[l]['passed'] else 'fail'} (CV {per[l]['aupr']['cv']['v0_1']:.3f}->{per[l]['aupr']['cv']['a3']:.3f}, "
                                                        f"DDR {per[l]['aupr']['ddr']['v0_1']:.3f}->{per[l]['aupr']['ddr']['a3']:.3f})" for l in lesions)
          + f"; app segmenter {'switched for ' + '/'.join(swap) if switched else 'unchanged'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grader-swap")
    g.add_argument("--name", required=True)
    g.add_argument("--adr", required=True)
    g.add_argument("--candidate", required=True)
    g.add_argument("--baseline", action="append", help="split=run_id")
    g.add_argument("--baseline-app", action="store_true", help="comparator = the app grader's latest runs (ADR-018a, ADR-021)")
    g.add_argument("--require-recall-g1-gain", metavar="SPLIT", help="also require the stage-1 recall gain CI above 0 on SPLIT (ADR-021)")
    g.add_argument("--apply-as", choices=["grader", "fusion"], default="grader")
    g.add_argument("--candidate-latest", action="store_true", help="use the latest registry runs of the candidate model name")
    g.add_argument("--candidate-run", action="append", help="split=run_id (skip evaluation)")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--require-app-grader", help="apply only if this spec is the app grader at decision time")
    g.set_defaults(fn=cmd_grader_swap)
    sg = sub.add_parser("seg-swap")
    sg.add_argument("--name", required=True)
    sg.add_argument("--base-cv", default="v0-recipe-cv+pp_v2")
    sg.add_argument("--new-cv", required=True)
    sg.add_argument("--base", default="v0+pp_v2")
    sg.add_argument("--new", required=True, help="registry model name of the new segmenter + pp")
    sg.add_argument("--new-spec", required=True)
    sg.add_argument("--new-pp", required=True)
    sg.add_argument("--base-pp", default="configs/postprocess/pp_v2.json")
    sg.add_argument("--apply", action="store_true")
    sg.add_argument("--adr", default="ADR-016")
    sg.add_argument("--base-from-app", action="store_true", help="per lesion, compare with the segmenter the app uses now")
    sg.add_argument("--lesions", help="comma-separated subset, e.g. MA")
    sg.set_defaults(fn=cmd_seg_swap)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
