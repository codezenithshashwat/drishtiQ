"""Step 4 experiments (ADR-041) in plain words, generated from their result files; used by the About page and KEY_NUMBERS.

Negative results are kept on purpose: "we tested X; it did not help" is part of the evidence.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETS = ("IDRiD-val", "APTOS-val")
NAMES = {"idrid_grading_val": "IDRiD-val", "aptos_val": "APTOS-val"}


def _load(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def _pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def _delta(v):
    d = v["delta_coverage"]
    return f"{100 * d['delta']:+.1f} points [{100 * d['ci95'][0]:+.1f}, {100 * d['ci95'][1]:+.1f}]"


def _miss(v):
    a = v["alternative"]
    return f"missed {a['missed']}/{a['referable']} (upper bound {_pct(a['miss_rate_upper95'])})"


def rows():
    """One row per experiment: name, question, verdict (adopt / abandon / not testable / reported), what we found."""
    s4 = _load("results/step4/step4_results.json") or {}
    fa = _load("results/faithfulness.json")
    r1 = _load("results/robustness/r1_robustness.json")
    out = []
    a = s4.get("a_disagreement")
    if a:
        e = a["enrichment_among_would_be_routine_2_5pct"]
        v = a["routing_with_flag"]["validation"]
        caught = sum(m["flagged"] for m in a["known_misses_2_5pct"].values())
        out.append(dict(key="disagreement", name="Lesion map vs grade disagreement",
                        question="Among images the grader would route to routine, does a high haemorrhage/exudate count flag the referable ones?",
                        verdict="abandon" if a["rule"]["verdict"] == "ABANDON" else "adopt",
                        found=f"Healthy (grade-0) training images already show many segmented spots with the current segmenter (90th percentile "
                              f"{a['grade0_reference']['he_ex_percentiles']['90']:.0f} haemorrhage/exudate regions), so the flag threshold is "
                              f"{a['chosen_threshold_HE_EX']} regions. Relative risk {e['pooled']['rr']:.1f} [{e['pooled']['rr_ci95'][0]:.2f}, "
                              f"{e['pooled']['rr_ci95'][1]:.0f}] (includes 1); coverage change at 2.5%: "
                              + "; ".join(f"{n} {_delta(v[n]['0.025'])}" for n in SETS)
                              + f". It caught {caught} of the {len(a['known_misses_2_5pct'])} known misses. Limited by the current segmenter's lesion quality."))
    b = s4.get("b_ood")
    if b:
        out.append(dict(key="ood", name="Out-of-distribution score",
                        question="Does distance from the training data (grader embedding) flag unfamiliar images and reduce misses?",
                        verdict="abandon" if b["rule"]["verdict"] == "ABANDON" else "adopt",
                        found=f"Separates IDRiD from APTOS images with AUROC {b['auroc_dataset_shift_idrid_vs_aptos']:.2f} (needed ≥ 0.70); synthetic "
                              f"degradations AUROC {b['auroc_synthetic_pooled']:.2f} (darkening {b['auroc_synthetic_by_kind']['dark']:.2f}). Missed referable "
                              f"images among routed: {b['missed_pooled']['pinned']} without, {b['missed_pooled']['with_gate']} with the gate."))
    c = s4.get("c_referable_head")
    if c:
        v = c["primary_head_vs_pinned"]["validation"]
        out.append(dict(key="referable_head", name="Separate referable-DR output",
                        question="Does a model trained with its own 'referable' output route more images safely than the stage score?",
                        verdict="abandon" if c["primary_head_vs_pinned"]["rule"]["verdict"] == "ABANDON" else "adopt",
                        found="Coverage change at 2.5%: " + "; ".join(f"{n} {_delta(v[n]['0.025'])}, {_miss(v[n]['0.025'])}" for n in SETS)
                              + ". The extra coverage on APTOS-val came with misses above the 4.5% tolerance."))
    d = s4.get("d_ensemble")
    if d:
        v = d["validation"]
        out.append(dict(key="ensemble", name="Seed ensemble for routing",
                        question="Do several training runs averaged route more images safely than one?",
                        verdict="not testable",
                        found="Only one extra seed exists (two needed; no new seeds trained). Two-run average, descriptive only, at 2.5%: "
                              + "; ".join(f"{n} {_delta(v[n]['0.025'])}, {_miss(v[n]['0.025'])}" for n in SETS) + "."))
    if fa:
        res = fa["results"]
        out.append(dict(key="faithfulness", name="Explanation faithfulness",
                        question="Does hiding the lesions an explanation cites lower the AI score more than hiding an equal area elsewhere?",
                        verdict="adopt" if fa["claim_supported"] else "abandon",
                        found="; ".join(f"{NAMES.get(k, k)}: median drop {v['median_drop_cited']:.2f} vs {v['median_drop_control']:.2f} (n = {v['n']}, "
                                        f"p = {v['p_value']:.1g})" for k, v in res.items())
                              + ". The explanations point at regions that drive the score (development data)."))
    if r1:
        worst = []
        for split, levels in r1["results"].items():
            for lvl, m in levels.items():
                pc = (m.get("policy_c") or {}).get("0.025")
                if pc and lvl != "none_0":
                    worst.append((pc["missed"] / max(pc["referable"], 1), split, lvl, pc, m["quality_flagged"]))
        if worst:
            rate, split, lvl, pc, qf = max(worst)
            clean = {s: r1["results"][s]["none_0"]["policy_c"]["0.025"] for s in r1["results"] if r1["results"][s]["none_0"].get("policy_c")}
            out.append(dict(key="robustness", name="Degraded photos (blur, low light, JPEG, downscaling, rotation)",
                            question="How do grading and the routine pile behave on poorer photos?",
                            verdict="reported",
                            found="Clean photos: " + "; ".join(f"{NAMES.get(s, s)} {c_['missed']}/{c_['referable']} referable routed to routine"
                                                                 for s, c_ in clean.items())
                                  + f". Worst degradation: {lvl.replace('_', ' ')} on {NAMES.get(split, split)}: {pc['missed']}/{pc['referable']} referable "
                                    f"routed to routine, while the quality check flagged only {_pct(qf, 0)} of the photos at that level. "
                                    "Strong blur, low contrast and very dark photos are mostly flagged by the quality check, so they shrink "
                                    "the routine pile instead. Details: results/robustness/r1_robustness.json."))
    return out
