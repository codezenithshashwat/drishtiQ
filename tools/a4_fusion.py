"""A4 lesion-to-grade fusion (ADR-021): extract features, fit on the inner hold-out, register IDRiD-val/APTOS-val runs.

    .venv\\Scripts\\python tools\\a4_fusion.py

Features come from the app grader and the app segmenter (as configured after the A3 decision). They are cached to
results/cache/a4/ every 100 images, so a retried job resumes. Writes configs/fusion/a4_v1.json and two registry
grading runs with model name "fusion:configs/fusion/a4_v1.json"; tools/rules.py then applies ADR-021.
"""
import csv
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
from data.fingerprint import fingerprint, hamming_matrix, to_bits  # noqa: E402
from eval import data, metrics, registry  # noqa: E402
from finetune_mixed import POOL  # noqa: E402
from inference import postprocess as pp  # noqa: E402
from inference.finetuned import FinetunedGrader  # noqa: E402
from inference.fusion import FEATURES, features  # noqa: E402
from inference.pipeline import DISPLAY, LesionSegmenter, default_device  # noqa: E402

APP = json.loads((ROOT / "configs/app/app.json").read_text())
OUT = ROOT / "configs/fusion/a4_v1.json"
CACHE = ROOT / "results/cache/a4"
AUDIT = ROOT / "results/audit"
MODEL_NAME = "fusion:configs/fusion/a4_v1.json"


def read(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def inner_holdout_rows():
    pool = [data.load_split(s)[0] for s in POOL]
    y = np.concatenate([[int(r["DR_grade"]) for r in rows] for rows in pool])
    source = np.concatenate([[k] * len(rows) for k, rows in enumerate(pool)])
    strata = source * 5 + y
    _, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    flat = [(k, r) for k, rows in enumerate(pool) for r in rows]
    return [flat[i] for i in sorted(inner_va)]


def ddr_near(rows):
    """True for images within structure-hash distance 42 of any DDR lesion-segmentation image (ADR-021 exclusion)."""
    ddr = to_bits([r["shash"] for r in read(AUDIT / "ddr/ddr_seg_fingerprints.csv")])
    known = {}
    for f in ("aptos/aptos_fingerprints.csv", "aptos/idrid_all_fingerprints.csv", "mmrdr/mmrdr_cfp_fingerprints.csv"):
        for r in read(AUDIT / f):
            known[r["path"].replace("\\", "/")] = r["shash"]
    hashes = [known.get(r["filepath"].replace("\\", "/")) or fingerprint(ROOT / r["filepath"])["shash"] for _, r in rows]
    return hamming_matrix(to_bits(hashes), ddr).min(1) <= 42


def extract(name, rows, grader, seg):
    key = hashlib.sha256(json.dumps([APP["grader"], APP.get("segmenter"), [r["filepath"] for _, r in rows]]).encode()).hexdigest()[:10]
    path = CACHE / f"{name}_{key}.npz"
    done = dict(np.load(path, allow_pickle=True)) if path.exists() else {"x": np.zeros((0, len(FEATURES)))}
    xs = list(done["x"])
    for i in range(len(xs), len(rows)):
        im = data.load_image(rows[i][1]["filepath"])
        _, score = grader.predict(im)
        scale = DISPLAY / max(im.size)
        size = (round(im.width * scale), round(im.height * scale))
        masks, fov = seg.masks(im, size, pp.locate_optic_disc(im))
        xs.append(features(score, {k: v[1] for k, v in masks.items()}, fov))
        if (i + 1) % 100 == 0 or i + 1 == len(rows):
            CACHE.mkdir(parents=True, exist_ok=True)
            np.savez(path, x=np.array(xs))
            print(f"{name}: {i + 1}/{len(rows)}", flush=True)
    return np.array(xs)


def main():
    if not APP["grader"].startswith("finetune:"):
        raise SystemExit("ADR-021 needs a regression grader score")
    device = default_device()
    grader = FinetunedGrader(sorted(glob.glob(str(ROOT / APP["grader"].removeprefix("finetune:")))), device)
    seg = LesionSegmenter(APP, device)

    inner = inner_holdout_rows()
    near = ddr_near(inner)
    train = [x for x, n in zip(inner, near) if not n]
    print(f"inner hold-out {len(inner)}; {int(near.sum())} excluded as near-copies of DDR lesion images", flush=True)
    x_tr = extract("inner", train, grader, seg)
    y_tr = np.array([int(r["DR_grade"]) for _, r in train])
    mean, std = x_tr.mean(0), x_tr.std(0) + 1e-9
    lr = LogisticRegression(C=1.0, max_iter=2000).fit((x_tr - mean) / std, y_tr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(adr="ADR-021", features=FEATURES, mean=mean.tolist(), std=std.tolist(), coef=lr.coef_.tolist(),
                                   intercept=lr.intercept_.tolist(), grader=APP["grader"], segmenter=APP.get("segmenter"),
                                   fitted_on=f"inner hold-out, {len(train)} images ({int(near.sum())} DDR near-copies excluded)"), indent=2))

    for split in ("idrid_grading_val", "aptos_val"):
        rows, sha = data.load_split(split)
        x = extract(split, [(None, r) for r in rows], grader, seg)
        probs = lr.predict_proba((x - mean) / std)
        y = np.array([int(r["DR_grade"]) for r in rows])
        m = metrics.grading_metrics(y, probs)
        p, c = m["point"], m["ci95"]
        row = dict(description="A4 fusion: logistic regression on grader score + lesion counts/areas (ADR-021)",
                   train_data=f"fine-tuner inner hold-out ({len(train)})", eval_overlap="no", eval_split=split, n_images=m["n"], split_sha256=sha[:12],
                   qwk=p["qwk"], qwk_ci=registry.ci(c["qwk"]), macro_f1=p["macro_f1"], macro_f1_ci=registry.ci(c["macro_f1"]),
                   recall_g1_ci=registry.ci(c["recall_g1"]), severe_under=p["severe_under"], severe_under_ci=registry.ci(c["severe_under"]),
                   referable_sens=p["referable_sens"], referable_spec=p["referable_spec"], notes=f"support {m['support']}",
                   **{f"recall_g{k}": p[f"recall_g{k}"] for k in range(5)})
        run_id, folder = registry.record("grade", MODEL_NAME, row, m, dict(task="grade", model=MODEL_NAME, split=split, fusion=str(OUT)))
        preds = [dict(image=r.get("image_id") or r.get("id_code"), DR_grade=r["DR_grade"], predicted=int(pr.argmax()),
                      **{f"p{k}": f"{pr[k]:.5f}" for k in range(5)}) for r, pr in zip(rows, probs)]
        data.write_csv(folder / f"predictions_{split}.csv", preds, list(preds[0]))
        (ROOT / "queue/decisions").mkdir(parents=True, exist_ok=True)
        (ROOT / f"queue/decisions/a4_run_{split}.txt").write_text(run_id)
        print(f"RESULT: A4 fusion {split}: QWK {p['qwk']:.3f}, stage-1 recall {p['recall_g1']:.2f} (run {run_id})", flush=True)


if __name__ == "__main__":
    main()
