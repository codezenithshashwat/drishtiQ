"""Approach V2, Step 4 (ADR-041): four routing experiments, run but never integrated into the decision path.

    .venv\\Scripts\\python tools\\step4_experiments.py embed      # GPU: scores / embeddings (pinned s17, s23, regbin s17)
    .venv\\Scripts\\python tools\\step4_experiments.py segment    # GPU: lesion burden for (a), app segmenter
    .venv\\Scripts\\python tools\\step4_experiments.py analyse    # CPU: verdicts, results/step4/*.json, registry rows

(a) global/local disagreement, (b) OOD score, (c) separate referable head, (d) seed ensemble. Every threshold, Platt map,
confidence map and tau is fitted on the fine-tuner's internal hold-out only; IDRiD-val and APTOS-val only verify.
Comparator: the pinned grader with policy (c) (ADR-039/040). Pre-registered rules: ADR-041.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
sys.path.insert(0, str(ROOT / "tools"))
from coverage_step2 import CAL, CKPT, CKPT_SHA, cp_upper, fit_threshold, quality_flags  # noqa: E402
from eval import data, registry  # noqa: E402
from finetune_mixed import POOL, cached, to_input  # noqa: E402
from sklearn.covariance import LedoitWolf  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedShuffleSplit  # noqa: E402

GRADERS = ROOT / "models/checkpoints/phase2/graders"
S23 = GRADERS / "convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s23.pt"
REGBIN = GRADERS / "convnext_tiny_mixed_regbin_plain384_datasetbal_sqrtcw_v1_s17.pt"
OUT = ROOT / "results/step4"
CACHE = ROOT / "results/cache/step4"
VAL = {"idrid_grading_val": "IDRiD-val", "aptos_val": "APTOS-val"}
LEVELS = ("0.025", "0.05")
TAUS = [round(0.50 + 0.05 * i, 2) for i in range(10)]
DEGRADE = ("blur", "dark", "noise", "jpeg")
SEED = 17


# ---- data ------------------------------------------------------------------------------------------------------------
def pool():
    """Pool rows in fine-tuner order and the inner split (same strata and seed as finetune_mixed)."""
    splits = [data.load_split(s)[0] for s in POOL]
    rows = [r for rs in splits for r in rs]
    source = np.concatenate([[k] * len(rs) for k, rs in enumerate(splits)])
    y = np.array([int(r["DR_grade"]) for r in rows])
    strata = source * 5 + y
    tr, va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    return splits, rows, source, y, np.sort(tr), np.sort(va)


def degrade(batch, kind, rng):
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    x = batch.astype(np.float32)
    if kind == "blur":
        x = np.stack([gaussian_filter(b, (4, 4, 0)) for b in x])
    elif kind == "dark":
        x = x * 0.35
    elif kind == "noise":
        x = x + rng.normal(0, 25, x.shape)
    elif kind == "jpeg":
        import io
        out = []
        for b in batch:
            buf = io.BytesIO()
            Image.fromarray(b).save(buf, "JPEG", quality=5)
            out.append(np.asarray(Image.open(buf).convert("RGB")))
        x = np.stack(out).astype(np.float32)
    return np.clip(x, 0, 255).astype(np.uint8)


# ---- GPU: outputs and embeddings ---------------------------------------------------------------------------------------
def embed():
    import hashlib
    import torch
    from inference.finetuned import FinetunedGrader
    assert hashlib.sha256(CKPT.read_bytes()).hexdigest() == CKPT_SHA, "pinned checkpoint changed"
    CACHE.mkdir(parents=True, exist_ok=True)
    splits, rows, source, y, tr, va = pool()
    offsets = np.cumsum([0] + [len(s) for s in splits])
    arrays = {s: cached(s, splits[k], 384) for k, s in enumerate(POOL)}
    for s in VAL:
        arrays[s] = cached(s, data.load_split(s)[0], 384)

    def batches(split, idx, kind=None):
        rng = np.random.default_rng(SEED)
        for i in range(0, len(idx), 64):
            b = np.stack([arrays[split][j] for j in idx[i:i + 64]])
            yield degrade(b, kind, rng) if kind else b

    @torch.no_grad()
    def run(model, gen, want_emb):
        outs, embs = [], []
        for b in gen:
            with torch.autocast("cuda"):
                f = model.forward_features(to_input(b, "cuda", False))
                e = model.forward_head(f, pre_logits=True)
                o = model.head.fc(e)
            outs.append(o.float().cpu().numpy())
            if want_emb:
                embs.append(e.float().cpu().numpy())
        return np.concatenate(outs), (np.concatenate(embs) if want_emb else None)

    for name, path, full in (("s17", CKPT, True), ("s23", S23, False), ("regbin", REGBIN, False)):
        target = CACHE / f"outputs_{name}.npz"
        if target.exists() or not path.exists():
            print(f"{name}: {'cached' if target.exists() else 'checkpoint missing, skipped'}", flush=True)
            continue
        model = FinetunedGrader([path], "cuda").models[0]
        t0, res = time.perf_counter(), {}
        # Pool: the pinned grader runs on every image (OOD fit needs the training side); the others on the hold-out only.
        for k, s in enumerate(POOL):
            local = np.arange(len(splits[k])) if full else np.array([i - offsets[k] for i in va if source[i] == k])
            o, e = run(model, batches(s, local), full)
            res[f"pool_{s}_out"], res[f"pool_{s}_idx"] = o, local
            if full:
                res[f"pool_{s}_emb"] = e
        for s in VAL:
            idx = np.arange(len(arrays[s]))
            res[f"{s}_out"], e = run(model, batches(s, idx), full)
            if full:
                res[f"{s}_emb"] = e
                for kind in DEGRADE:
                    res[f"{s}_{kind}_out"], res[f"{s}_{kind}_emb"] = run(model, batches(s, idx, kind), True)
        np.savez_compressed(target, **res)
        print(f"{name}: done in {time.perf_counter() - t0:.0f}s", flush=True)
        del model
        torch.cuda.empty_cache()


# ---- shared routing machinery ------------------------------------------------------------------------------------------
def stage(s, t):
    return np.searchsorted(np.asarray(t), s, side="right")


def margin(s, t):
    return np.min(np.abs(s[:, None] - np.asarray(t)[None]), 1)


class System:
    """Score -> stage / confidence (ADR-019) and P(referable) (Platt), all fitted on the hold-out."""

    def __init__(self, s_in, y_in, thresholds, ref_logit_in=None, cal=None):
        self.t = list(thresholds)
        if cal is not None:  # the pinned grader: production calibration file
            self.iso_x, self.iso_y, self.tau = cal["isotonic"]["x"], cal["isotonic"]["y"], cal["tau"]
        else:
            correct = (stage(s_in, self.t) == y_in).astype(float)
            iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(margin(s_in, self.t), correct)
            self.iso_x, self.iso_y = list(iso.X_thresholds_), list(iso.y_thresholds_)
            conf = self.conf(s_in)
            ok = [x for x in TAUS if (conf >= x).any() and correct[conf >= x].mean() >= 0.85]
            self.tau = min(ok) if ok else 0.95
        x_in = s_in if ref_logit_in is None else ref_logit_in
        self.platt = LogisticRegression(C=1e6).fit(x_in[:, None], (y_in >= 2).astype(int))

    def conf(self, s):
        return np.interp(margin(s, self.t), self.iso_x, self.iso_y)

    def p_ref(self, x):
        return self.platt.predict_proba(x[:, None])[:, 1]


def routed(p, elig, t):
    return elig & (p < t)


def summary(r, ref):
    n_ref, k = int(ref.sum()), int((r & ref).sum())
    return dict(units=int(len(r)), referable=n_ref, routed=int(r.sum()), coverage=float(r.mean()), missed=k,
                miss_rate=k / n_ref if n_ref else None, miss_rate_upper95=cp_upper(k, n_ref))


def paired_delta(r_alt, r_base, rng, n=2000):
    i = rng.integers(0, len(r_alt), (n, len(r_alt)))
    d = r_alt[i].mean(1) - r_base[i].mean(1)
    return dict(delta=float(r_alt.mean() - r_base.mean()), ci95=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))])


def adopt_rule(per_set):
    """ADR-041: at 2.5%, delta CI > 0 on >= 1 set, lower bound > -0.03 on the other, verified miss rate <= 4.5% on both."""
    d = [per_set[n]["0.025"]["delta_coverage"]["ci95"] for n in VAL.values()]
    miss_ok = all(per_set[n]["0.025"]["alternative"]["miss_rate"] <= 0.045 for n in VAL.values())
    gain = any(lo > 0 for lo, _ in d) and all(lo > -0.03 for lo, _ in d)
    return dict(coverage_gain=bool(gain), miss_tolerance_ok=bool(miss_ok), verdict="ADOPT-candidate" if gain and miss_ok else "ABANDON")


def compare(base, alt, ref, rng):
    """base/alt: {level: routed bool array}."""
    return {lvl: dict(pinned=summary(base[lvl], ref), alternative=summary(alt[lvl], ref),
                      delta_coverage=paired_delta(alt[lvl], base[lvl], rng)) for lvl in LEVELS}


# ---- analysis ----------------------------------------------------------------------------------------------------------
def load(name):
    return dict(np.load(CACHE / f"outputs_{name}.npz"))


def holdout_view(o, rows, source, va, key="out"):
    """Hold-out outputs in hold-out order (pool order restricted to the inner hold-out)."""
    splits_idx = {s: o[f"pool_{s}_idx"] for s in POOL}
    offs = np.cumsum([0] + [int((source == k).sum()) for k in range(len(POOL))])
    parts = []
    for k, s in enumerate(POOL):
        want = va[source[va] == k] - offs[k]
        pos = {int(j): n for n, j in enumerate(splits_idx[s])}
        parts.append(o[f"pool_{s}_{key}"][[pos[int(j)] for j in want]])
    return np.concatenate(parts)


def analyse():
    rng = np.random.default_rng(SEED)
    cal = json.loads(CAL.read_text())
    routing_cfg = json.loads((ROOT / "configs/routing/routing_v1.json").read_text())
    splits, rows, source, y, tr, va = pool()
    rows_in, y_in, ref_in = [rows[i] for i in va], y[va], y[va] >= 2
    q_in = quality_flags(rows_in, "coverage_quality_inner")
    val = {}
    for s, name in VAL.items():
        vr = data.load_split(s)[0]
        yy = np.array([int(r["DR_grade"]) for r in vr])
        val[name] = dict(split=s, rows=vr, y=yy, ref=yy >= 2, q=quality_flags(vr, f"coverage_quality_{s}"))

    o17 = load("s17")
    s_in17 = holdout_view(o17, rows, source, va)[:, 0]
    base_sys = System(s_in17, y_in, cal["thresholds"], cal=cal)
    elig_in17 = q_in & (base_sys.conf(s_in17) >= base_sys.tau)
    # The comparator is production: frozen Platt map and thresholds from configs/routing/routing_v1.json. Refitting them
    # here differs slightly (fp16 batch effects on the scores); the difference is recorded, not used.
    refit_t = {lvl: fit_threshold(base_sys.p_ref(s_in17), ref_in, elig_in17, float(lvl)) for lvl in LEVELS}
    base_sys.platt.coef_[:] = routing_cfg["platt"]["coef"]
    base_sys.platt.intercept_[:] = routing_cfg["platt"]["intercept"]
    p_in17 = base_sys.p_ref(s_in17)
    base_t = {lvl: float(routing_cfg["thresholds"][lvl]) for lvl in LEVELS}
    base = {}
    for name, v in val.items():
        s = o17[f"{v['split']}_out"][:, 0]
        v["s17"] = s
        v["elig17"] = v["q"] & (base_sys.conf(s) >= base_sys.tau)
        v["p17"] = base_sys.p_ref(s)
        base[name] = {lvl: routed(v["p17"], v["elig17"], base_t[lvl]) for lvl in LEVELS}
    results = dict(adr="ADR-041", comparator=dict(grader=str(CKPT.relative_to(ROOT)), policy="c", thresholds=base_t,
                                                   frozen_from="configs/routing/routing_v1.json", refit_here_for_reference=refit_t))

    def alternative(s_in, thresholds, val_scores, logit_in=None, val_logits=None, gate_in=None, val_gate=None):
        sysm = System(s_in, y_in, thresholds, ref_logit_in=logit_in)
        e_in = q_in & (sysm.conf(s_in) >= sysm.tau) & (gate_in if gate_in is not None else True)
        p_in = sysm.p_ref(logit_in if logit_in is not None else s_in)
        t = {lvl: fit_threshold(p_in, ref_in, e_in, float(lvl)) for lvl in LEVELS}
        per = {}
        for name, v in val.items():
            sv = val_scores[name]
            e = v["q"] & (sysm.conf(sv) >= sysm.tau) & (val_gate[name] if val_gate is not None else True)
            p = sysm.p_ref(val_logits[name] if val_logits is not None else sv)
            per[name] = compare(base[name], {lvl: routed(p, e, t[lvl]) for lvl in LEVELS}, v["ref"], rng)
        return dict(tau=sysm.tau, thresholds=t, validation=per), sysm

    # (d) ensemble of the seed runs that exist
    if (CACHE / "outputs_s23.npz").exists():
        o23 = load("s23")
        cfg23 = json.loads(S23.with_suffix(".json").read_text())
        t_ens = np.mean([cal["thresholds"], cfg23["thresholds"]], 0)
        s_in = (s_in17 + holdout_view(o23, rows, source, va)[:, 0]) / 2
        vs = {n: (v["s17"] + o23[f"{v['split']}_out"][:, 0]) / 2 for n, v in val.items()}
        res, _ = alternative(s_in, t_ens, vs)
        res["members"] = [CKPT.name, S23.name, "(s41 never trained; queue stopped)"]
        res["rule"] = adopt_rule(res["validation"])
        results["d_ensemble"] = res

    # (c) separate referable head
    if (CACHE / "outputs_regbin.npz").exists():
        ob = load("regbin")
        cfgb = json.loads(REGBIN.with_suffix(".json").read_text())
        hin = holdout_view(ob, rows, source, va)
        vs = {n: ob[f"{v['split']}_out"][:, 0] for n, v in val.items()}
        vl = {n: ob[f"{v['split']}_out"][:, 1] for n, v in val.items()}
        head, sysb = alternative(hin[:, 0], cfgb["thresholds"], vs, logit_in=hin[:, 1], val_logits=vl)
        head["rule"] = adopt_rule(head["validation"])
        derived, _ = alternative(hin[:, 0], cfgb["thresholds"], vs)
        # secondary: the same model's head vs its own derived P(referable)
        within = {}
        for name, v in val.items():
            e = v["q"] & (sysb.conf(vs[name]) >= sysb.tau)
            r_head = {lvl: routed(sysb.p_ref(vl[name]), e, head["thresholds"][lvl]) for lvl in LEVELS}
            r_der = {lvl: routed(System(hin[:, 0], y_in, cfgb["thresholds"]).p_ref(vs[name]), e, derived["thresholds"][lvl]) for lvl in LEVELS}
            within[name] = {lvl: paired_delta(r_head[lvl], r_der[lvl], rng) for lvl in LEVELS}
        results["c_referable_head"] = dict(primary_head_vs_pinned=head, secondary_derived_vs_pinned=derived,
                                           secondary_head_vs_own_derived=within, inner_qwk=cfgb["inner_qwk"], best_epoch=cfgb["best_epoch"])

    # (b) OOD score: Mahalanobis on the pinned grader's pre-logit embedding
    emb = {s: o17[f"pool_{s}_emb"] for s in POOL}
    offs = np.cumsum([0] + [len(sp) for sp in splits])
    all_emb = np.concatenate([emb[s] for s in POOL])
    fit_all = LedoitWolf().fit(all_emb[tr])
    aptos_k = POOL.index("aptos_train")
    fit_aptos = LedoitWolf().fit(all_emb[tr[source[tr] == aptos_k]])
    d_ap = {n: fit_aptos.mahalanobis(o17[f"{v['split']}_emb"]) for n, v in val.items()}
    auroc_dataset = float(roc_auc_score(np.r_[np.ones(len(d_ap["IDRiD-val"])), np.zeros(len(d_ap["APTOS-val"]))],
                                        np.r_[d_ap["IDRiD-val"], d_ap["APTOS-val"]]))
    clean = np.concatenate([fit_all.mahalanobis(o17[f"{v['split']}_emb"]) for v in val.values()])
    per_kind, pooled_deg = {}, []
    for kind in DEGRADE:
        deg = np.concatenate([fit_all.mahalanobis(o17[f"{v['split']}_{kind}_emb"]) for v in val.values()])
        per_kind[kind] = float(roc_auc_score(np.r_[np.ones(len(deg)), np.zeros(len(clean))], np.r_[deg, clean]))
        pooled_deg.append(deg)
    pooled_deg = np.concatenate(pooled_deg)
    auroc_synth = float(roc_auc_score(np.r_[np.ones(len(pooled_deg)), np.zeros(len(clean))], np.r_[pooled_deg, clean]))
    d_in = fit_all.mahalanobis(holdout_view(o17, rows, source, va, "emb"))
    cut = float(np.percentile(d_in, 95))
    gate_val = {n: fit_all.mahalanobis(o17[f"{v['split']}_emb"]) < cut for n, v in val.items()}
    ood, _ = alternative(s_in17, cal["thresholds"], {n: v["s17"] for n, v in val.items()}, gate_in=d_in < cut, val_gate=gate_val)
    miss_base = sum(ood["validation"][n][lvl]["pinned"]["missed"] for n in VAL.values() for lvl in LEVELS)
    miss_gate = sum(ood["validation"][n][lvl]["alternative"]["missed"] for n in VAL.values() for lvl in LEVELS)
    # degraded images: does the pinned policy (c) route them, and does the gate catch them?
    degraded_routing = {}
    for kind in DEGRADE:
        r_list, g_list = [], []
        for n, v in val.items():
            s = o17[f"{v['split']}_{kind}_out"][:, 0]
            e = v["q"] & (base_sys.conf(s) >= base_sys.tau)  # quality flags from the clean image (the gate reads full-size images)
            r_list.append(routed(base_sys.p_ref(s), e, base_t["0.025"]))
            g_list.append(fit_all.mahalanobis(o17[f"{v['split']}_{kind}_emb"]) < cut)
        r, g = np.concatenate(r_list), np.concatenate(g_list)
        ref = np.concatenate([v["ref"] for v in val.values()])
        degraded_routing[kind] = dict(routed_by_pinned_c=int(r.sum()), referable_routed=int((r & ref).sum()),
                                      of_which_blocked_by_gate=int((r & ~g).sum()), referable_blocked=int((r & ref & ~g).sum()))
    abandon_b = auroc_dataset < 0.70 or auroc_synth < 0.70 or not miss_gate < miss_base
    results["b_ood"] = dict(method="Mahalanobis (Ledoit-Wolf) on pinned s17 pre-logit embedding (768-d)", gate_cut_holdout_p95=cut,
                            auroc_dataset_shift_idrid_vs_aptos=auroc_dataset, auroc_synthetic_pooled=auroc_synth, auroc_synthetic_by_kind=per_kind,
                            routing_with_gate=ood, missed_pooled=dict(pinned=miss_base, with_gate=miss_gate),
                            degraded_inputs_at_2_5pct=degraded_routing,
                            rule=dict(verdict="ABANDON" if abandon_b else "ADOPT-candidate",
                                      auroc_ok=bool(auroc_dataset >= 0.70 and auroc_synth >= 0.70), fewer_misses=bool(miss_gate < miss_base)))

    # (a) global/local disagreement
    burden_path = CACHE / "burden_app_segmenter.json"
    bjson = json.loads(burden_path.read_text()) if burden_path.exists() else {}
    if bjson.get("complete"):
        burden = bjson["burden"]
        def counts(rr, key):
            return np.array([burden[r["filepath"]][key] if r["filepath"] in burden else -1 for r in rr])

        def heex(rr):
            return np.array([burden[r["filepath"]]["HE"] + burden[r["filepath"]]["EX"] if r["filepath"] in burden else -1 for r in rr])

        ref0 = [dict(filepath=r["filepath"]) for r in bjson["grade0_reference"]]
        b0, m0 = heex(ref0), counts(ref0, "MA")
        k_ma = max(1, int(np.ceil(np.percentile(m0, 99.5))))
        cands = sorted({max(1, int(np.ceil(np.percentile(b0, q)))) for q in (90, 95, 97.5, 99)})
        r_in = routed(p_in17, elig_in17, base_t["0.025"])
        b_in, ma_in = heex(rows_in), counts(rows_in, "MA")
        assert (b_in[r_in] >= 0).all(), "routed hold-out images without a burden value"
        chosen, budget = None, []
        for k in cands:  # most sensitive (lowest) threshold within the 5% referral budget
            extra = float((r_in & ((b_in >= k) | (ma_in >= k_ma))).mean())
            budget.append(dict(threshold_HE_EX=k, extra_review_rate_holdout=extra))
            if chosen is None and extra <= 0.05:
                chosen = k
        if chosen is None:
            chosen = cands[-1]
        flag = lambda rr: (heex(rr) >= chosen) | (counts(rr, "MA") >= k_ma)  # noqa: E731
        flag_in = flag(rows_in)
        flag_val = {n: flag(v["rows"]) for n, v in val.items()}
        dis, _ = alternative(s_in17, cal["thresholds"], {n: v["s17"] for n, v in val.items()}, gate_in=~flag_in,
                             val_gate={n: ~f for n, f in flag_val.items()})
        for lvl in LEVELS:
            assert dis["thresholds"][lvl] < bjson["p_cap"], "refitted threshold above the segmented range"
        enrich, pooled = {}, [0, 0, 0, 0]
        for n, v in val.items():
            r = base[n]["0.025"]
            assert (heex(v["rows"])[r] >= 0).all()
            f, ref = flag_val[n][r], v["ref"][r]
            cells = [int((f & ref).sum()), int((f & ~ref).sum()), int((~f & ref).sum()), int((~f & ~ref).sum())]
            pooled = [a + c for a, c in zip(pooled, cells)]
            enrich[n] = dict(flagged=int(f.sum()), flagged_referable=cells[0], unflagged=int((~f).sum()), unflagged_referable=cells[2],
                             extra_review_rate=float(f.sum() / len(v["y"])), **katz(*cells))
        enrich["pooled"] = katz(*pooled) | dict(cells=pooled)
        rule = adopt_rule(dis["validation"])
        rr_excludes_1 = enrich["pooled"]["rr_ci95"][0] > 1
        rule["rr_ci_excludes_1"] = bool(rr_excludes_1)
        rule["verdict"] = "ADOPT-candidate" if rule["verdict"] == "ADOPT-candidate" and rr_excludes_1 else "ABANDON"
        misses = {}
        for n, v in val.items():
            for i in np.flatnonzero(base[n]["0.025"] & v["ref"]):
                r = v["rows"][i]
                misses[r["filepath"].split("/")[-1]] = dict(set=n, grade=int(v["y"][i]), **burden[r["filepath"]], flagged=bool(flag_val[n][i]))
        results["a_disagreement"] = dict(segmenter=bjson["segmenter"], flag="HE + EX components >= k_HE_EX, or MA components >= k_MA",
                                         grade0_reference=dict(n=len(b0), he_ex_percentiles={str(q): float(np.percentile(b0, q)) for q in (90, 95, 97.5, 99)},
                                                               ma_p99_5=float(np.percentile(m0, 99.5))),
                                         k_MA=k_ma, candidates=budget, chosen_threshold_HE_EX=chosen, known_misses_2_5pct=misses, enrichment_among_would_be_routine_2_5pct=enrich,
                                         routing_with_flag=dis, rule=rule)

    if "--dry" in sys.argv:  # code check only: print verdicts, write and register nothing
        print(json.dumps({k: (v.get("rule") or v.get("primary_head_vs_pinned", {}).get("rule")) for k, v in results.items() if isinstance(v, dict)}, indent=1))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "step4_results.json").write_text(json.dumps(results, indent=2))
    for key, label in (("a_disagreement", "disagreement"), ("b_ood", "ood"), ("c_referable_head", "referable_head"), ("d_ensemble", "ensemble")):
        if key not in results:
            print(f"{key}: not run (inputs missing)", flush=True)
            continue
        r = results[key]
        rule = r["rule"] if "rule" in r else r["primary_head_vs_pinned"]["rule"]
        per = (r.get("routing_with_flag") or r.get("routing_with_gate") or r.get("primary_head_vs_pinned") or r)["validation"]
        for split, name in VAL.items():
            v = per[name]["0.025"]
            registry.record("step4", f"step4:{label}", dict(
                description=f"ADR-041 Step 4 ({label}), policy (c) at 2.5%, development data; not integrated (results/step4/step4_results.json)",
                eval_overlap="no", eval_split=split, n_images=v["alternative"]["units"],
                notes=f"verdict {rule['verdict']}; dcoverage {v['delta_coverage']['delta']:+.4f} {registry.ci(v['delta_coverage']['ci95'])}; "
                      f"miss {v['alternative']['missed']}/{v['alternative']['referable']}"), results[key], dict(task="step4", experiment=label))
            time.sleep(1.1)
        print(f"RESULT {key}: {rule['verdict']}", flush=True)


def katz(a, b, c, d):
    """Relative risk of referable, flagged (a referable, b not) vs unflagged (c, d); Katz log CI, +0.5 in empty cells."""
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    rr = (a / (a + b)) / (c / (c + d))
    se = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    return dict(rr=float(rr), rr_ci95=[float(np.exp(np.log(rr) - 1.96 * se)), float(np.exp(np.log(rr) + 1.96 * se))])


# ---- GPU: lesion burden with the app segmenter -------------------------------------------------------------------------
def segment():
    import torch  # noqa: F401
    from scipy import ndimage as ndi
    from inference import postprocess as pp
    from inference.pipeline import DISPLAY, LESIONS, LesionSegmenter
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    seg = LesionSegmenter(app, "cuda")
    cal = json.loads(CAL.read_text())
    p_cap = 0.5
    splits, rows, source, y, tr, va = pool()
    o17 = load("s17")
    s_in = holdout_view(o17, rows, source, va)[:, 0]
    cfg_platt = LogisticRegression(C=1e6).fit(s_in[:, None], (y[va] >= 2).astype(int))
    conf = lambda s: np.interp(margin(s, cal["thresholds"]), cal["isotonic"]["x"], cal["isotonic"]["y"])  # noqa: E731
    todo = []
    rows_in = [rows[i] for i in va]
    q_in = quality_flags(rows_in, "coverage_quality_inner")
    keep = q_in & (conf(s_in) >= cal["tau"]) & (cfg_platt.predict_proba(s_in[:, None])[:, 1] < p_cap)
    todo += [r for r, k in zip(rows_in, keep) if k]
    for s in VAL:
        vr = data.load_split(s)[0]
        sv = o17[f"{s}_out"][:, 0]
        k = quality_flags(vr, f"coverage_quality_{s}") & (conf(sv) >= cal["tau"]) & (cfg_platt.predict_proba(sv[:, None])[:, 1] < p_cap)
        todo += [r for r, kk in zip(vr, k) if kk]
    rng = np.random.default_rng(SEED)
    grade0 = []
    for k in range(len(POOL)):
        cand = [i for i in tr if source[i] == k and y[i] == 0]
        grade0 += [rows[i] for i in rng.choice(cand, min(300, len(cand)), replace=False)]
    todo += grade0
    path = CACHE / "burden_app_segmenter.json"
    store = json.loads(path.read_text()) if path.exists() else {}
    burden = store.get("burden", {})
    t0, done = time.perf_counter(), 0
    for n, r in enumerate(todo):
        if r["filepath"] in burden:
            continue
        im = data.load_image(r["filepath"])
        scale = DISPLAY / max(im.size)
        size = (round(im.width * scale), round(im.height * scale))
        od = pp.locate_optic_disc(im)
        masks, _ = seg.masks(im, size, od)
        counts = {k: int(ndi.label(masks[k][1], np.ones((3, 3)))[1]) for k in LESIONS}
        burden[r["filepath"]] = dict(counts, HE_EX_SE=counts["HE"] + counts["EX"] + counts["SE"])
        done += 1
        if done % 100 == 0:
            print(f"{n + 1}/{len(todo)} ({(time.perf_counter() - t0) / done:.2f}s/image)", flush=True)
            path.write_text(json.dumps(dict(segmenter=app.get("segmenter") or "v0 + pp_v2 (app default)", p_cap=p_cap,
                                            grade0_reference=[dict(filepath=g["filepath"]) for g in grade0], burden=burden)))
    path.write_text(json.dumps(dict(segmenter=app.get("segmenter") or "v0 + pp_v2 (app default)", p_cap=p_cap, complete=True,
                                    grade0_reference=[dict(filepath=g["filepath"]) for g in grade0], burden=burden)))
    print(f"segment: {len(todo)} images, {done} new, {time.perf_counter() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    {"embed": embed, "segment": segment, "analyse": analyse}[sys.argv[1]]()
