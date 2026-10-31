"""Explanation faithfulness test (ADR-032, ADR-032a): does hiding the lesions an explanation cites lower the grade score
more than hiding an equal area elsewhere?

    .venv\\Scripts\\python tools\\faithfulness.py

For IDRiD-val and APTOS-val images the app grades >= 2: the app's analysis gives the explanation (cited lesion types)
and the lesion masks at display size. Cited regions (dilated 5 px) are filled by harmonic inpainting; the control fills
an equal total area of random discs inside the FOV and outside every segmented lesion (seed 17). Outcome: drop in the
grader's regression score versus the unmodified display image. One-sided Wilcoxon signed-rank, cited vs control.
"""
import base64
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eval import data, registry  # noqa: E402
from inference import Pipeline  # noqa: E402
from inference.system import system_name  # noqa: E402

OUT = ROOT / "results/faithfulness.json"


def decode(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64.split(",", 1)[-1])))


def harmonic_inpaint(img, mask, iters=200):
    """Fill mask by 3x3 mean diffusion from the boundary (ADR-032a)."""
    out = img.astype(np.float32).copy()
    for c in range(3):
        ch = out[..., c]
        ch[mask] = ch[~mask].mean()
        for _ in range(iters):
            ch[mask] = ndi.uniform_filter(ch, 3)[mask]
    return np.clip(out, 0, 255).astype(np.uint8)


def control_mask(fov, lesions, area, rng, radius=8):
    allowed = fov & ~ndi.binary_dilation(lesions, iterations=10)
    ys, xs = np.nonzero(allowed)
    m = np.zeros_like(fov)
    yy, xx = np.ogrid[:fov.shape[0], :fov.shape[1]]
    for _ in range(10000):
        if m.sum() >= area or not len(ys):
            break
        k = rng.integers(len(ys))
        m |= ((yy - ys[k]) ** 2 + (xx - xs[k]) ** 2 <= radius ** 2) & allowed
    return m


def latest_predictions(name, split):
    rows = [r for r in csv.DictReader(open(ROOT / "results/registry.csv", encoding="utf-8")) if r["task"] == "grade" and r["model"] == name and r["eval_split"] == split]
    if not rows:
        return None
    return {r["image"]: int(r["predicted"]) for r in csv.DictReader(open(next((ROOT / "results/runs" / rows[-1]["run_id"]).glob("predictions_*.csv")), encoding="utf-8"))}


def main():
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    pipe = Pipeline()
    grader = pipe.grader
    rng = np.random.default_rng(17)
    results = {}
    for split in ("idrid_grading_val", "aptos_val"):
        rows, _ = data.load_split(split)
        preds = latest_predictions(system_name(app), split) or {}
        cited_d, control_d, skipped = [], [], 0
        for r in rows:
            image_id = r.get("image_id") or r.get("id_code")
            if preds and preds.get(image_id, 0) < 2:
                continue
            a = pipe.analyze((ROOT / r["filepath"]).read_bytes())
            if a.get("status") != "ok" or a["grading"]["grade"] < 2:
                continue
            refs = sorted({l for s in a.get("explanations", []) for l in (s.get("refs") or {}).get("lesions", [])})
            disp = np.asarray(decode(a["display_image"]).convert("RGB"))
            masks = {l["key"]: np.asarray(decode(l["overlay"]))[..., 3] == 230 for l in a["lesions"]}
            cited = np.zeros(disp.shape[:2], bool)
            for l in refs:
                cited |= masks.get(l, False)
            if cited.sum() == 0:
                skipped += 1
                continue
            cited = ndi.binary_dilation(cited, iterations=5)
            fov = disp.max(2) > 15
            ctrl = control_mask(fov, np.any(list(masks.values()), 0), int(cited.sum()), rng)
            base = grader.predict(Image.fromarray(disp))[1]
            s_cited = grader.predict(Image.fromarray(harmonic_inpaint(disp, cited)))[1]
            s_ctrl = grader.predict(Image.fromarray(harmonic_inpaint(disp, ctrl)))[1]
            cited_d.append(base - s_cited)
            control_d.append(base - s_ctrl)
        cd, kd = np.array(cited_d), np.array(control_d)
        p = float(wilcoxon(cd, kd, alternative="greater").pvalue) if len(cd) > 5 else float("nan")
        results[split] = dict(n=int(len(cd)), skipped_no_cited_lesion=skipped, median_drop_cited=float(np.median(cd)) if len(cd) else None,
                              median_drop_control=float(np.median(kd)) if len(kd) else None, mean_drop_cited=float(cd.mean()) if len(cd) else None,
                              mean_drop_control=float(kd.mean()) if len(kd) else None, p_value=p)
        print(split, results[split], flush=True)
    supported = all(v["p_value"] < 0.05 for v in results.values())
    summary = dict(adr="ADR-032", grader=system_name(app), results=results, claim_supported=bool(supported))
    OUT.write_text(json.dumps(summary, indent=2))
    run_id, _ = registry.record("faithfulness", system_name(app), dict(description="Explanation faithfulness test (results/faithfulness.json)",
                                eval_overlap="no", eval_split="idrid_grading_val+aptos_val", notes=f"claim supported: {supported}"), summary, dict(task="faithfulness"))
    print(f"RESULT: ADR-032 faithfulness {'SUPPORTED' if supported else 'NOT supported'}: " + "; ".join(
        f"{s.split('_')[0]} n={v['n']} median drop cited {v['median_drop_cited']:.3f} vs control {v['median_drop_control']:.3f}, p={v['p_value']:.3g}"
        for s, v in results.items() if v["n"]) + f" (run {run_id})", flush=True)


if __name__ == "__main__":
    main()
