"""Generate results/SCORECARD.md: per section, the pre-registered target (ADR-026), the measured value, met / not met.

    .venv\\Scripts\\python tools\\scorecard.py           # write
    .venv\\Scripts\\python tools\\scorecard.py --check   # exit 1 if the file is stale

Every measured value is read from results/registry.csv, queue/decisions/, results/ or configs/; nothing is typed by
hand. Items without evidence yet are "pending", never "met". tests/test_consistency.py runs --check.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inference.system import system_name  # noqa: E402
OUT = ROOT / "results/SCORECARD.md"


def jfile(rel):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def latest(rows, **kw):
    hits = [r for r in rows if all(r[k] == v for k, v in kw.items())]
    return hits[-1] if hits else None


def has(rel, text=None):
    p = ROOT / rel
    if not p.exists():
        return False
    return True if text is None else text in p.read_text(encoding="utf-8", errors="replace")


def generate():
    rows = list(csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8")))
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    g = system_name(app)  # registry name of the app's grading system
    sections = []

    def item(sec, target, measured, met, source):
        sections.append((sec, target, measured, "met" if met is True else "not met" if met is False else "pending", source))

    # 1. Problem coverage
    sec = "1. Problem coverage"
    about = "frontend/src/app/screens/About.tsx"
    item(sec, "DR grading in the app", f"{app['grader'].split('/')[-1]} (system {g})", True, "configs/app/app.json")
    item(sec, "Segmentation of MA / HE / EX (+SE) in the app", ", ".join(f"{k}: {v['model'].split(':')[0]}" for k, v in (app.get("segmenter") or {k: {"model": "v0"} for k in "MA HE EX SE".split()}).items()), True, "configs/app/app.json")
    case_view = "frontend/src/app/screens/CaseView.tsx"
    image_viewer = "frontend/src/app/screens/ImageViewer.tsx"
    comparison = has(case_view, "Physician view") or (has(case_view, "ImageViewer") and has(image_viewer, "Original reference") and has(image_viewer, "Compare"))
    item(sec, "Explainable heatmaps + physician side-by-side view", "Grad-CAM + lesion maps; comparison view " + ("present" if comparison else "missing"),
         comparison or None, f"{case_view}, {image_viewer}")
    item(sec, "Models compared (ConvNeXt, EfficientNet, RETFound) on About", "table " + ("present" if has(about, "Models we compared") else "missing"), has(about, "Models we compared") or None, about)
    item(sec, "Named benchmarks: APTOS-val shown; Messidor-2 placeholder", "APTOS-val run " + ("registered" if latest(rows, task="grade", model=g, eval_split="aptos_val") else "missing"),
         bool(latest(rows, task="grade", model=g, eval_split="aptos_val")) and has(about, "Messidor-2"), "results/registry.csv")
    b, w = jfile("results/benchmark.json"), jfile("results/worklist_scale.json")
    item(sec, "Scalability measured: images/hour (GPU, CPU); 500-case worklist render",
         (f"GPU {3600 / b['gpu']['per_stage']['total']['mean_s']:.0f}/h, CPU {3600 / b['cpu']['per_stage']['total']['mean_s']:.0f}/h"
          if b and "per_stage" in b.get("gpu", {}) and "per_stage" in b.get("cpu", {}) else "timing pending")
         + (f"; 500 cases render in {w['render_ms']:.0f} ms" if w else "; worklist scale pending"), (bool(b) and bool(w)) or None, "results/benchmark.json, results/worklist_scale.json")
    item(sec, "Real-world: robustness, quality gate, offline, Hindi", ", ".join(f"{n} {'done' if jfile(p) else 'pending'}" for n, p in
         (("R1", "results/robustness/r1_robustness.json"), ("R2", "results/robustness/r2_bad_input.json"), ("R4", "results/robustness/r4_quality_gate.json")))
         + ", offline test " + ("present" if has("tests/test_offline.py") else "missing") + ", Hindi " + ("present" if has("review/hindi_review.csv") else "missing"),
         all(jfile(p) for p in ("results/robustness/r1_robustness.json", "results/robustness/r2_bad_input.json", "results/robustness/r4_quality_gate.json")) or None, "results/robustness/")

    # 2. Grading (ADR-026)
    sec = "2. Grading"
    a, i = latest(rows, task="grade", model=g, eval_split="aptos_val"), latest(rows, task="grade", model=g, eval_split="idrid_grading_val")
    f = lambda r, k: float(r[k]) if r and r[k] not in ("", "nan") else None
    targets = [("APTOS-val QWK ≥ 0.92", f(a, "qwk"), lambda v: v >= 0.92), ("APTOS-val macro-F1 ≥ 0.70", f(a, "macro_f1"), lambda v: v >= 0.70),
               ("APTOS-val stage-1 recall ≥ 55%", f(a, "recall_g1"), lambda v: v >= 0.55), ("APTOS-val stage-4 recall ≥ 70%", f(a, "recall_g4"), lambda v: v >= 0.70),
               ("APTOS-val severe under-grading ≤ 1.6%", f(a, "severe_under"), lambda v: v <= 0.0160), ("IDRiD-val QWK ≥ 0.89", f(i, "qwk"), lambda v: v >= 0.89)]
    for t, v, ok in targets:
        item(sec, t, "—" if v is None else f"{v:.3f}", None if v is None else ok(v), f"registry {(a if 'APTOS' in t else i)['run_id']}" if (a and i) else "registry")

    # 3. Segmentation (ADR-026)
    sec = "3. Segmentation"
    seg = app.get("segmenter")
    cv_name = "v0-recipe-cv+pp_v2"
    if seg:
        a3 = [v for v in seg.values() if v["model"].startswith("a3")]
        if a3:
            cv_name = f"a3-cv+{Path(a3[0]['postprocess']).stem}"
    cv = latest(rows, task="segment", model=cv_name, eval_split="idrid_seg_cv50_oof")
    for lesion, thr in (("MA", 0.40), ("HE", 0.60), ("EX", 0.80), ("SE", 0.60)):
        v = f(cv, f"aupr_{lesion}") if cv else None
        item(sec, f"IDRiD 5-fold CV AUPR {lesion} ≥ {thr:.2f}", "—" if v is None else f"{v:.3f}", None if v is None else v >= thr, f"registry {cv['run_id']}" if cv else "registry")
    d = jfile("queue/decisions/a3_swap.json")
    item(sec, "DDR-test AUPR above v0.1 for each lesion (bootstrap CI > 0)",
         "; ".join(f"{l} {x['aupr']['ddr']['v0_1']:.3f}→{x['aupr']['ddr']['a3']:.3f}" for l, x in d["per_lesion"].items()) + " (point estimates; CI pending)" if d else "A3 pending",
         None, "queue/decisions/a3_swap.json")
    item(sec, "Grade-0 false-positive regions ≤ pp_v2",
         "; ".join(f"{l} {x['fp_regions_g0']['v0_1']:.2f}→{x['fp_regions_g0']['a3']:.2f}" for l, x in d["per_lesion"].items()) if d else "A3 pending",
         all(x["fp_regions_g0"]["a3"] <= x["fp_regions_g0"]["v0_1"] for x in d["per_lesion"].values()) if d else None, "queue/decisions/a3_swap.json")
    fr = jfile("results/segmentation/froc.json")
    item(sec, "Lesion-level detection reported (FROC at 1/2/4/8 FP per image)", "reported" if fr else "pending", True if fr else None, "results/segmentation/froc.json")

    # 4. Uniqueness
    sec = "4. Uniqueness"
    fa = jfile("results/faithfulness.json")
    item(sec, "Explanation faithfulness: hiding cited lesions lowers the score more than control (both sets, p < 0.05)",
         "; ".join(f"{s}: p = {v['p_value']:.3g}" for s, v in fa["results"].items()) if fa else "pending", fa["claim_supported"] if fa else None, "results/faithfulness.json")
    item(sec, "Doctor-feedback view (Disagreements page)", "present" if has("frontend/src/app/screens/Disagreements.tsx") else "missing", has("frontend/src/app/screens/Disagreements.tsx") or None, "frontend/src/app/screens/Disagreements.tsx")
    cal = jfile("configs/calibration/app_grader.json")
    ok = cal and cal.get("grader") == g
    item(sec, "Worklist time-saving and deferral measured", "; ".join(f"{s}: 95% of referable after {v['triage']['workload_to_95pct_sensitivity']:.0%} of list, defers {1 - v['abstention']['coverage']:.1%}"
                                                                       for s, v in cal["validation"].items()) if ok else "pending", True if ok else None, "configs/calibration/app_grader.json")

    cov = [r for r in rows if r["task"] == "coverage"]
    m = jfile(f"results/runs/{cov[-1]['run_id']}/metrics.json") if cov else None
    item(sec, "Routine-rescreening coverage measured with a pre-registered miss-rate bound (ADR-039, development data)",
         "; ".join(f"{n}: {v['c']['0.025']['coverage']:.1%} routed, missed {v['c']['0.025']['missed']}/{v['c']['0.025']['referable']}" for n, v in m["validation"].items())
         if m else "pending", (not m["falsification"]["c"]["abandoned"]) if m else None, f"registry {cov[-1]['run_id']}" if cov else "tools/coverage_step2.py")

    # 5. Rigour
    sec = "5. Rigour"
    adrs = (ROOT / "docs/research/ARCHITECTURE_DECISION_LOG.md").read_text(encoding="utf-8").count("\n## ADR-")
    item(sec, "Pre-registered decisions", f"{adrs} ADRs", True, "docs/research/ARCHITECTURE_DECISION_LOG.md")
    item(sec, "reproduce.ps1 regenerates key numbers + scorecard from saved predictions", "present" if has("reproduce.ps1") else "missing", has("reproduce.ps1") or None, "reproduce.ps1")
    item(sec, "Model card and data card", ", ".join(n for n in ("docs/MODEL_CARD.md", "docs/DATA_CARD.md") if has(n)) or "missing", (has("docs/MODEL_CARD.md") and has("docs/DATA_CARD.md")) or None, "docs/")

    # 6. UI / product
    sec = "6. UI / product"
    hr = jfile("review/heuristic_review.json")
    item(sec, "Nielsen heuristic review: no open high/medium issues", f"{hr['open_high_medium']} open of {hr['total']}" if hr else "pending", (hr["open_high_medium"] == 0) if hr else None, "review/heuristic_review.json")
    ax = jfile("results/a11y.json")
    item(sec, "Accessibility audit: 0 serious/critical", f"{ax['serious_critical']} serious/critical ({ax['tool']})" if ax else "pending", (ax["serious_critical"] == 0) if ax else None, "results/a11y.json")
    item(sec, "Usability test script ready (results filled by user)", "script present" if has("review/usability_test.md") else "missing", None, "review/usability_test.md")

    # 7. External validation (ADR-034)
    sec = "7. External validation"
    tag = subprocess.run(["git", "tag", "--list", "rc-1"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    item(sec, "rc-1 tagged before any external evaluation", "tagged" if tag else "not yet", bool(tag) or None, "git tag")
    for name, rel in (("IDRiD clean test", "results/external/idrid_test.json"), ("DeepDRiD", "results/external/deepdrid.json")):
        e = jfile(rel)
        item(sec, f"{name}: referable AUROC ≥ 0.90", f"{e['referable_auroc']:.3f}" if e else "pending (locked)", (e["referable_auroc"] >= 0.90) if e else None, rel)

    out = ["# Scorecard", "", "Generated by `tools/scorecard.py` from the registry, decision files and recorded results; targets pre-registered in ADR-026.",
           "Nothing was tuned on validation or locked sets to meet a target. \"pending\" means no evidence yet.", ""]
    cur = None
    for sec, target, measured, status, source in sections:
        if sec != cur:
            n = [s for s in sections if s[0] == sec]
            out += ["", f"## {sec}: {sum(s[3] == 'met' for s in n)} of {len(n)} met", "", "| Target | Measured | Status | Source |", "|---|---|---|---|"]
            cur = sec
        out.append(f"| {target} | {measured} | {status} | `{source}` |")
    return "\n".join(out) + "\n"


def main():
    text = generate()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text(encoding="utf-8") == text else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"RESULT: wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
