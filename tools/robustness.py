"""R1-R4 safety checks (ADR-022..025). Inference only; nothing is trained or tuned here.

    .venv\\Scripts\\python tools\\robustness.py r1   # degradations on IDRiD-val + APTOS-val
    .venv\\Scripts\\python tools\\robustness.py r2   # non-fundus, blurred and dark inputs must never get a confident stage
    .venv\\Scripts\\python tools\\robustness.py r3   # Grad-CAM peak location audit
    .venv\\Scripts\\python tools\\robustness.py r4   # quality gate on DDR-train ungradable vs gradable images

Results: results/robustness/<check>.json and one registry row per check (task "safety").
"""
import glob
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import data, registry  # noqa: E402
from inference import assist, postprocess as pp  # noqa: E402
from inference.finetuned import FinetunedGrader, regression_to_grade  # noqa: E402
from inference.pipeline import DISPLAY, Pipeline, default_device  # noqa: E402

OUT = ROOT / "results/robustness"
APP = json.loads((ROOT / "configs/app/app.json").read_text())
VAL = ["idrid_grading_val", "aptos_val"]


def load_grader():
    if not APP["grader"].startswith("finetune:"):
        raise SystemExit("robustness checks expect a fine-tuned regression grader")
    return FinetunedGrader(sorted(glob.glob(str(ROOT / APP["grader"].removeprefix("finetune:")))), default_device())


def deferred(score, grader, cal):
    """ADR-019 deferral when calibrated for this grader; otherwise the app's uncalibrated margin rule (< 0.25)."""
    margin = float(np.min(np.abs(grader.thresholds - score)))
    if cal is None:
        return margin < 0.25
    return float(np.interp(margin, cal["isotonic"]["x"], cal["isotonic"]["y"])) < cal["tau"]


def assess(im, grader, cal):
    q = Pipeline.quality(im)
    if q["fov_fraction"] < 0.2:
        return dict(outcome="rejected", stage=None, score=None)
    _, score = grader.predict(im)
    stage = regression_to_grade(score, grader.thresholds)
    if not q["usable"]:
        return dict(outcome="quality_flag", stage=stage, score=score)
    if deferred(score, grader, cal):
        return dict(outcome="deferred", stage=stage, score=score)
    return dict(outcome="confident", stage=stage, score=score)


def record(check, model, summary, notes):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{check}.json").write_text(json.dumps(summary, indent=2))
    run_id, _ = registry.record("safety", f"{check}:{model}", dict(description=f"{check} (see results/robustness/{check}.json)", eval_overlap="no",
                                                                     eval_split=summary.get("split", "+".join(VAL)), notes=notes), summary, dict(task=check))
    return run_id


# ---- R1 ---------------------------------------------------------------------------------------------------------
def degrade(im, kind, level):
    if kind == "none":
        return im
    if kind == "blur":
        return im.filter(ImageFilter.GaussianBlur(level * im.width))
    if kind == "brightness":
        return ImageEnhance.Brightness(im).enhance(level)
    if kind == "contrast":
        return ImageEnhance.Contrast(im).enhance(level)
    if kind == "jpeg":
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=level)
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    if kind == "downscale":
        s = level / max(im.size)
        return im.resize((round(im.width * s), round(im.height * s)), Image.Resampling.BILINEAR) if s < 1 else im
    if kind == "rotate":
        return im.rotate(level, resample=Image.Resampling.BILINEAR)
    raise ValueError(kind)


R1_LEVELS = [("none", 0), ("blur", 0.002), ("blur", 0.005), ("brightness", 0.6), ("brightness", 0.35), ("contrast", 0.5),
             ("jpeg", 50), ("jpeg", 30), ("downscale", 1280), ("downscale", 640), ("rotate", 10)]


def routing_c(items, ref, routing_cfg):
    """Policy (c) per frozen routing config (ADR-039/040, Step 4f): only "confident" images (gate passed, confidence >= tau)
    with P(referable) below the frozen threshold are routed routine. Rejected / flagged / deferred images stay in the
    denominator."""
    from scipy.stats import beta
    out = {}
    for lvl, t in routing_cfg["thresholds"].items():
        routed = np.array([it["outcome"] == "confident" and
                           1 / (1 + np.exp(-(routing_cfg["platt"]["coef"] * it["score"] + routing_cfg["platt"]["intercept"]))) < t
                           for it in items])
        k, n = int((routed & ref).sum()), int(ref.sum())
        out[lvl] = dict(coverage=float(routed.mean()), routed=int(routed.sum()), missed=k, referable=n,
                        miss_rate=k / n if n else None, miss_rate_upper95=float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0)
    return out


def r1():
    grader, cal = load_grader(), assist.load_calibration(APP["grader"])
    routing_cfg = json.loads((ROOT / "configs/routing/routing_v1.json").read_text())
    out = {}
    for split in VAL:
        rows, _ = data.load_split(split)
        y = np.array([int(r["DR_grade"]) for r in rows])
        res = {f"{k}_{v}": [] for k, v in R1_LEVELS}
        for i, r in enumerate(rows):
            im = data.load_image(r["filepath"])
            for k, v in R1_LEVELS:
                res[f"{k}_{v}"].append(assess(degrade(im, k, v), grader, cal))
            if (i + 1) % 100 == 0:
                print(f"R1 {split} {i + 1}/{len(rows)}", flush=True)
        out[split] = {}
        for level, items in res.items():
            stage = np.array([-1 if it["stage"] is None else it["stage"] for it in items])
            graded = stage >= 0
            ref = y >= 2
            out[split][level] = dict(
                qwk=float(cohen_kappa_score(y[graded], stage[graded], weights="quadratic")) if graded.sum() > 1 else None,
                referable_sensitivity=float(((stage >= 2) & ref).sum() / max(ref.sum(), 1)),
                referable_specificity=float(((stage < 2) & ~ref & graded).sum() / max((~ref).sum(), 1)),
                quality_flagged=float(np.mean([it["outcome"] in ("rejected", "quality_flag") for it in items])),
                deferred=float(np.mean([it["outcome"] == "deferred" for it in items])),
                policy_c=routing_c(items, ref, routing_cfg) if routing_cfg["pinned_sha256"] == grader.checkpoints[Path(APP["grader"]).name] else None)
    summary = dict(adr="ADR-022", grader=APP["grader"], calibrated=cal is not None, results=out)
    run = record("r1_robustness", Path(APP["grader"]).stem, summary, "per-degradation QWK, referable sens/spec, quality-flag and deferral rates")
    worst = min(((s, l, v["qwk"]) for s, d in out.items() for l, v in d.items() if v["qwk"] is not None), key=lambda t: t[2])
    print(f"RESULT: R1 done (run {run}); clean QWK " + ", ".join(f"{s.split('_')[0]} {d['none_0']['qwk']:.3f}" for s, d in out.items())
          + f"; worst {worst[0].split('_')[0]} {worst[1]} QWK {worst[2]:.3f}", flush=True)


# ---- R2 ---------------------------------------------------------------------------------------------------------
def synthetic(rng, n=64, size=(1024, 768)):
    w, h = size
    for i in range(n):
        kind = i % 8
        if kind == 0:
            a = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
        elif kind == 1:
            g = np.linspace(0, 255, w)[None, :, None] * np.ones((h, 1, 3))
            a = (g * rng.random(3)).astype(np.uint8)
        elif kind == 2:
            c = ((np.arange(w)[None] // 64 + np.arange(h)[:, None] // 64) % 2) * 255
            a = np.repeat(c[..., None], 3, 2).astype(np.uint8)
        elif kind == 3:
            a = np.full((h, w, 3), rng.integers(0, 256, 3), np.uint8)
        else:
            a = np.full((h, w, 3), 255 if kind == 4 else rng.integers(30, 220), np.uint8)
        im = Image.fromarray(a)
        d = ImageDraw.Draw(im)
        if kind in (4, 5):  # text "screenshots"
            for line in range(20):
                d.text((20, 20 + 30 * line), f"Report line {line}: lorem ipsum value {rng.integers(1000)}", fill=(0, 0, 0))
        if kind in (6, 7):  # random shapes, including a single orange disc that mimics a fundus outline
            for _ in range(12):
                x0, y0 = int(rng.integers(0, w - 50)), int(rng.integers(0, h - 50))
                d.ellipse([x0, y0, x0 + int(rng.integers(20, 400)), y0 + int(rng.integers(20, 400))], fill=tuple(int(v) for v in rng.integers(0, 256, 3)))
            if kind == 7:
                d.ellipse([w // 2 - 300, h // 2 - 300, w // 2 + 300, h // 2 + 300], fill=(190, 90, 40))
        yield f"synthetic_{i:02d}_kind{kind}", im


def r2():
    grader, cal = load_grader(), assist.load_calibration(APP["grader"])
    rng = np.random.default_rng(17)
    items = list(synthetic(rng))
    dev = [r for r in data.load_split("idrid_grading_devtrain")[0]]
    for r in [dev[i] for i in rng.choice(len(dev), 20, replace=False)]:
        im = data.load_image(r["filepath"])
        items.append((f"blurred_{r['image_id']}", im.filter(ImageFilter.GaussianBlur(0.02 * im.width))))
        items.append((f"dark_{r['image_id']}", ImageEnhance.Brightness(im).enhance(0.15)))
    results = []
    for name, im in items:
        a = assess(im.convert("RGB"), grader, cal)
        results.append(dict(name=name, **a))
    fails = [r for r in results if r["outcome"] == "confident"]
    by_group = {}
    for r in results:
        g = r["name"].split("_")[0]
        by_group.setdefault(g, {}).setdefault(r["outcome"], 0)
        by_group[g][r["outcome"]] += 1
    summary = dict(adr="ADR-023", grader=APP["grader"], calibrated=cal is not None, n=len(results), by_group=by_group,
                   failures=fails, passed=not fails, split="synthetic + idrid_grading_devtrain (training side)")
    run = record("r2_bad_input", Path(APP["grader"]).stem, summary, f"{len(fails)} of {len(results)} bad inputs got a confident stage")
    print(f"RESULT: R2 {'PASS' if not fails else 'FAIL'}: {len(fails)} of {len(results)} bad inputs got a confident stage {by_group} (run {run})", flush=True)


# ---- R3 ---------------------------------------------------------------------------------------------------------
def r3():
    grader = load_grader()
    out = {}
    for split in VAL:
        rows, _ = data.load_split(split)
        counts = dict(border=0, optic_disc=0, glare=0, retina=0)
        per_image = []
        for r in rows:
            im = data.load_image(r["filepath"])
            scale = DISPLAY / max(im.size)
            size = (round(im.width * scale), round(im.height * scale))
            _, _, cam, _, _ = grader.grade_with_cam(im, size)
            fov = pp.fov_mask(im, size, 0.0)
            cam = np.where(fov, cam, 0)
            py, px = np.unravel_index(int(np.argmax(cam)), cam.shape)
            ys, xs = np.nonzero(fov)
            cy, cx, rad = ys.mean(), xs.mean(), np.sqrt(fov.sum() / np.pi)
            od = pp.locate_optic_disc(im)
            green = np.asarray(im.resize(size))[..., 1].astype(np.float32)
            win = green[max(0, py - 7):py + 8, max(0, px - 7):px + 8]
            if rad - np.hypot(py - cy, px - cx) < 0.05 * rad:
                where = "border"
            elif np.hypot(px - od[0] * scale, py - od[1] * scale) <= 1.5 * od[2] * scale:
                where = "optic_disc"
            elif win.mean() > np.percentile(green[fov], 99):
                where = "glare"
            else:
                where = "retina"
            counts[where] += 1
            per_image.append(dict(image=r.get("image_id") or r.get("id_code"), peak=where))
        n = len(rows)
        out[split] = dict(n=n, fractions={k: v / n for k, v in counts.items()}, shortcut_fraction=(n - counts["retina"]) / n, per_image=per_image)
    warn = any(v["shortcut_fraction"] > 0.10 for v in out.values())
    summary = dict(adr="ADR-024", grader=APP["grader"], results=out, warning_rule_triggered=warn)
    run = record("r3_gradcam_audit", Path(APP["grader"]).stem, summary, "Grad-CAM peak location: border / optic disc / glare / retina")
    print("RESULT: R3 " + "; ".join(f"{s.split('_')[0]} non-retina peaks {v['shortcut_fraction']:.1%} {({k: round(f, 3) for k, f in v['fractions'].items()})}"
                                    for s, v in out.items()) + f"; warning {'ON' if warn else 'off'} (run {run})", flush=True)


# ---- R4 ---------------------------------------------------------------------------------------------------------
def r4():
    sys.path.insert(0, str(ROOT / "src"))
    from data.extract_ddr import open_archive
    rng = np.random.default_rng(17)
    with open_archive() as z:
        names = {i.filename: i for i in z.infolist()}
        label_file = next(n for n in names if n.endswith("DR_grading/train.txt"))
        labels = [line.split() for line in z.read(label_file).decode().splitlines() if line.strip()]
        folder = label_file[:-len("train.txt")] + "train/"
        ungradable = [f for f, l in labels if l == "5"]
        gradable = [f for f, l in labels if l in "01234"]
        sample = list(rng.choice(gradable, len(ungradable), replace=False))
        res = {}
        for group, files in (("ungradable", ungradable), ("gradable", sample)):
            flags = []
            for k, f in enumerate(files):
                with z.open(names[folder + f]) as fh:
                    im = Image.open(io.BytesIO(fh.read())).convert("RGB")
                q = Pipeline.quality(im)
                flags.append(not q["usable"])
                if (k + 1) % 200 == 0:
                    print(f"R4 {group} {k + 1}/{len(files)}", flush=True)
            res[group] = dict(n=len(files), flagged=float(np.mean(flags)))
    summary = dict(adr="ADR-025", split="DDR grading train (training side)", results=res,
                   sensitivity_for_ungradable=res["ungradable"]["flagged"], specificity_on_gradable=1 - res["gradable"]["flagged"])
    run = record("r4_quality_gate", "quality_gate", summary, "DDR-train ungradable vs gradable flag rates")
    print(f"RESULT: R4 quality gate flags {res['ungradable']['flagged']:.1%} of {res['ungradable']['n']} DDR ungradable and "
          f"{res['gradable']['flagged']:.1%} of {res['gradable']['n']} gradable images (run {run})", flush=True)


if __name__ == "__main__":
    {"r1": r1, "r2": r2, "r3": r3, "r4": r4}[sys.argv[1]]()
