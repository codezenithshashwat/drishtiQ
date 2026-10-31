"""Approach V2, Step 2 (ADR-039): safe screening coverage of the pinned grader. No training; inference only.

    .venv\\Scripts\\python tools\\coverage_step2.py

Pinned grader (checkpoint hash checked). P(referable) = logistic calibration of the regression score on the internal
hold-out (isotonic as a secondary check). Policies (thresholds fitted ONLY on the internal hold-out, then verified):
  (a) P(referable) < t                      (b) (a) + quality gate passes            (c) (b) + ADR-019 stage confidence >= tau
Coverage = routed ROUTINE / all units (rejected/flagged stay in the denominator); miss rate = referable routed ROUTINE /
all referable, with an exact Clopper-Pearson 95% upper bound; coverage CI by bootstrap. Units are images.
Outputs: results/coverage/step2_baseline.json, results/coverage/curve.png (no fundus images), one registry row per set.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
sys.path.insert(0, str(ROOT / "tools"))
from eval import data, registry  # noqa: E402
from finetune_mixed import POOL  # noqa: E402
from inference.finetuned import FinetunedGrader  # noqa: E402
from inference.pipeline import Pipeline  # noqa: E402
from pseudo_label import teacher_scores  # noqa: E402

CKPT = ROOT / "models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt"
CKPT_SHA = "acf53697500919cf7c281652c10b12c48e77896ed366a7383a78a432cbef37a1"
CAL = ROOT / "configs/calibration/app_grader.json"
OUT = ROOT / "results/coverage"
LEVELS = (0.05, 0.025, 0.01)
VAL = {"idrid_grading_val": "IDRiD-val", "aptos_val": "APTOS-val"}


def quality_flags(rows, cache_name):
    """True where the quality gate passes (usable and not rejected); cached because it reads full-size images."""
    p = ROOT / f"results/cache/{cache_name}.json"
    cache = json.loads(p.read_text()) if p.exists() else {}
    for r in rows:
        if r["filepath"] not in cache:
            q = Pipeline.quality(data.load_image(r["filepath"]))
            cache[r["filepath"]] = bool(q["usable"] and q["fov_fraction"] >= 0.2)
    p.write_text(json.dumps(cache))
    return np.array([cache[r["filepath"]] for r in rows])


def inner_holdout(grader):
    pool = [data.load_split(s)[0] for s in POOL]
    y = np.concatenate([[int(r["DR_grade"]) for r in rows] for rows in pool])
    source = np.concatenate([[k] * len(rows) for k, rows in enumerate(pool)])
    strata = source * 5 + y
    _, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    offsets = np.cumsum([0] + [len(r) for r in pool])
    rows, scores = [], []
    for k, split in enumerate(POOL):
        local = [int(i - offsets[k]) for i in inner_va if source[i] == k]
        scores.append(teacher_scores(grader, split, pool[k], local))
        rows += [pool[k][i] for i in local]
    return rows, np.concatenate(scores)


def confidence(scores, cal):
    m = np.min(np.abs(scores[:, None] - np.asarray(cal["thresholds"])[None]), 1)
    return np.interp(m, cal["isotonic"]["x"], cal["isotonic"]["y"])


def fit_threshold(p_ref, ref, eligible, m):
    """Largest t such that the hold-out miss rate of routing (eligible & p_ref < t) is <= m."""
    cands = np.unique(np.r_[0.0, p_ref])
    best = 0.0
    n_ref = ref.sum()
    for t in cands:
        miss = ((p_ref < t) & eligible & ref).sum() / n_ref
        if miss <= m:
            best = t
        else:
            break
    return float(best)


def cp_upper(k, n):
    return float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0


def verify(p_ref, ref, eligible, t, rng):
    routed = eligible & (p_ref < t)
    n, n_ref = len(ref), int(ref.sum())
    k = int((routed & ref).sum())
    boot = []
    for _ in range(2000):
        i = rng.integers(0, n, n)
        boot.append(routed[i].mean())
    return dict(units=n, referable=n_ref, routed=int(routed.sum()), coverage=float(routed.mean()),
                coverage_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                missed=k, miss_rate=k / n_ref if n_ref else None, miss_rate_upper95=cp_upper(k, n_ref),
                sensitivity=1 - k / n_ref if n_ref else None,
                specificity=float((routed & ~ref).sum() / max((~ref).sum(), 1)),
                npv_routine=float(1 - k / routed.sum()) if routed.sum() else None, review_rate=float(1 - routed.mean()))


def main():
    assert hashlib.sha256(CKPT.read_bytes()).hexdigest() == CKPT_SHA, "pinned checkpoint changed"
    cal = json.loads(CAL.read_text())
    grader = FinetunedGrader([CKPT])
    assert np.allclose(grader.thresholds, cal["thresholds"]), "calibration file is not for the pinned grader"
    rng = np.random.default_rng(17)

    rows_in, s_in = inner_holdout(grader)
    y_in = np.array([int(r["DR_grade"]) for r in rows_in])
    ref_in = y_in >= 2
    q_in = quality_flags(rows_in, "coverage_quality_inner")
    platt = LogisticRegression(C=1e6).fit(s_in[:, None], ref_in.astype(int))
    iso = IsotonicRegression(out_of_bounds="clip").fit(s_in, ref_in.astype(float))
    p_in = platt.predict_proba(s_in[:, None])[:, 1]
    conf_in = confidence(s_in, cal)
    elig_in = {"a": np.ones(len(y_in), bool), "b": q_in, "c": q_in & (conf_in >= cal["tau"])}
    thresholds = {pol: {str(m): fit_threshold(p_in, ref_in, e, m) for m in LEVELS} for pol, e in elig_in.items()}
    holdout = {pol: {str(m): verify(p_in, ref_in, e, thresholds[pol][str(m)], rng) for m in LEVELS} for pol, e in elig_in.items()}

    results, curves = {}, {}
    dme = {r["content_hash"]: int(r["DME_label"]) for r in data.read_csv(data.GRADING_TRAIN_MANIFEST)}
    for split, name in VAL.items():
        rows, _ = data.load_split(split)
        s = teacher_scores(grader, split, rows)
        y = np.array([int(r["DR_grade"]) for r in rows])
        ref = y >= 2
        q = quality_flags(rows, f"coverage_quality_{split}")
        p = platt.predict_proba(s[:, None])[:, 1]
        conf = confidence(s, cal)
        elig = {"a": np.ones(len(y), bool), "b": q, "c": q & (conf >= cal["tau"])}
        res = {pol: {str(m): verify(p, ref, e, thresholds[pol][str(m)], rng) for m in LEVELS} for pol, e in elig.items()}
        if split == "idrid_grading_val":  # secondary referable definition: grade >= 2 OR macular-oedema risk >= 1
            ref2 = ref | np.array([dme.get(r["content_hash"], 0) >= 1 for r in rows])
            res["secondary_definition_c"] = {str(m): verify(p, ref2, elig["c"], thresholds["c"][str(m)], rng) for m in LEVELS}
        iso_p = iso.predict(s)
        res["isotonic_check_c"] = {str(m): verify(iso_p, ref, elig["c"], fit_threshold(iso.predict(s_in), ref_in, elig_in["c"], m), rng) for m in LEVELS}
        results[name] = res
        sweep = np.unique(np.r_[0.0, p, 1.01])
        curves[name] = {pol: [(float(((e & (p < t)) & ref).sum() / ref.sum()), float((e & (p < t)).mean())) for t in sweep] for pol, e in elig.items()}

    rule3 = {name: dict(referable=int(results[name]["a"]["0.05"]["referable"]),
                        upper95_if_zero_misses=cp_upper(0, int(results[name]["a"]["0.05"]["referable"])),
                        approx_3_over_n=3 / results[name]["a"]["0.05"]["referable"],
                        certifiable_levels=[m for m in LEVELS if cp_upper(0, int(results[name]["a"]["0.05"]["referable"])) <= m])
             for name in VAL.values()}

    def falsified(pol):
        near_zero_both = all(results[n][pol]["0.025"]["coverage_ci95"][0] <= 0 for n in VAL.values())
        over_tol = [n for n in VAL.values() if results[n][pol]["0.025"]["miss_rate"] > 0.045]
        return dict(coverage_ci_includes_0_on_both=near_zero_both, miss_rate_over_tolerance_on=over_tol, abandoned=bool(near_zero_both or over_tol))
    verdict = {pol: falsified(pol) for pol in ("a", "b", "c")}

    OUT.mkdir(parents=True, exist_ok=True)
    summary = dict(adr="ADR-039", grader=str(CKPT.relative_to(ROOT)), checkpoint_sha256=CKPT_SHA, units="images",
                   p_referable="logistic calibration of the regression score on the internal hold-out",
                   holdout=dict(n=int(len(y_in)), referable=int(ref_in.sum()), quality_pass=float(q_in.mean()), thresholds=thresholds, results=holdout),
                   validation=results, rule_of_three=rule3, falsification=verdict,
                   patient_level="not possible on development data (no eye pairs); deferred to the locked DeepDRiD / Messidor-2 evaluation")
    (OUT / "step2_baseline.json").write_text(json.dumps(summary, indent=2))
    plot(curves, results)
    for split, name in VAL.items():
        r = results[name]["c"]["0.025"]
        registry.record("coverage", "pinned:reg384_s17", dict(description="ADR-039 Step 2: safe screening coverage, policy (c) at 2.5% (results/coverage/step2_baseline.json)",
                        eval_overlap="no", eval_split=split, n_images=r["units"], referable_sens=r["sensitivity"], referable_spec=r["specificity"],
                        notes=f"coverage {r['coverage']:.4f} {registry.ci(r['coverage_ci95'])}; miss {r['missed']}/{r['referable']} (upper95 {r['miss_rate_upper95']:.4f})"),
                        summary, dict(task="coverage"))
    print("RESULT: Step 2 done; " + "; ".join(f"{n}: policy c at 2.5% coverage {results[n]['c']['0.025']['coverage']:.1%} "
                                             f"miss {results[n]['c']['0.025']['missed']}/{results[n]['c']['0.025']['referable']}" for n in VAL.values()))


def plot(curves, results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    labels = {"a": "(a) P(referable) only", "b": "(b) + quality gate", "c": "(c) + quality + confidence"}
    colors = {"a": "#94A3B8", "b": "#0D9488", "c": "#0F172A"}
    for ax, (name, cur) in zip(axes, curves.items()):
        for pol, pts in cur.items():
            ax.plot([100 * x for x, _ in pts], [100 * c for _, c in pts], label=labels[pol], color=colors[pol], lw=1.8)
        for m in LEVELS:
            r = results[name]["c"][str(m)]
            ax.scatter([100 * r["miss_rate"]], [100 * r["coverage"]], color="#DC2626", zorder=5, s=18)
        for m in LEVELS:
            ax.axvline(100 * m, color="#CBD5E1", lw=0.8, ls="--")
        ax.set_xlim(0, 20)
        ax.set_title(name)
        ax.set_xlabel("Miss rate: referable cases routed to routine (%)")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Coverage: share of all images routed to routine (%)")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Safe screening coverage vs miss rate (thresholds fitted on the internal hold-out; red = operating points of policy c)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "curve.png", dpi=150)


if __name__ == "__main__":
    main()
