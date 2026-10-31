"""ADR-018 pseudo-labels for APTOS test_images (unlabelled). Record-only experiment; never changes the app.

    .venv\\Scripts\\python tools\\pseudo_label.py

1. Leak check: structure hash of every APTOS test image vs IDRiD-val, APTOS-val and the IDRiD locked test (hashes from
   the audit files, so no locked-test pixels are read). Distance <= 42 -> dropped.
2. Teacher = the app grader (must be a finetune: grader). Its regression score on the fine-tuner's inner hold-out fixes
   d: the largest of {0.10, 0.20, 0.30, 0.40} with accuracy >= 0.90 on retained hold-out images, where an image is
   retained if its score is within d of the nearest grade (0-4) and its label is that grade.
3. The same rule labels the APTOS test pool. Output: data/interim/pseudo/aptos_test_pl_v1.csv (+ queue/decisions).
"""
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
from data.fingerprint import fingerprint, hamming_matrix, to_bits  # noqa: E402
from eval import data  # noqa: E402
from finetune_mixed import POOL, cached, predict  # noqa: E402
from inference.finetuned import FinetunedGrader  # noqa: E402

AUDIT = ROOT / "results/audit/aptos"
OUT = ROOT / "data/interim/pseudo/aptos_test_pl_v1.csv"
D_GRID, MIN_ACC, LEAK = [0.10, 0.20, 0.30, 0.40], 0.90, 42


def read(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def leak_check(test_paths):
    fp_file = AUDIT / "aptos_test_fingerprints.csv"
    if not fp_file.exists():
        rows = [dict(path=p, **{k: v for k, v in fingerprint(ROOT / p).items() if k in ("sha256", "shash")}) for p in test_paths]
        with open(fp_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["path", "sha256", "shash"])
            w.writeheader()
            w.writerows(rows)
    test = {r["path"]: r["shash"] for r in read(fp_file)}
    aptos = {r["id_code"]: r["shash"] for r in read(AUDIT / "aptos_fingerprints.csv")}
    idrid = {r["sha256"]: r["shash"] for r in read(AUDIT / "idrid_all_fingerprints.csv")}
    train_manifest = {r["content_hash"]: r["file_sha256"] for r in read(data.GRADING_TRAIN_MANIFEST)}
    refs = dict(aptos_val=[aptos[r["id_code"]] for r in data.load_split("aptos_val")[0]],
                idrid_val=[idrid[train_manifest[r["content_hash"]]] for r in data.load_split("idrid_grading_val")[0]],
                idrid_locked_test=[idrid[r["file_sha256"]] for r in read(ROOT / "data/interim/manifests/idrid_grading_test_clean.csv")
                                   if r["file_sha256"] in idrid])
    paths = list(test)
    h = to_bits([test[p] for p in paths])
    near = np.zeros(len(paths), bool)
    counts = {}
    for name, ref in refs.items():
        hit = hamming_matrix(h, to_bits(ref)).min(1) <= LEAK
        counts[name] = dict(reference_images=len(ref), test_images_within_42=int(hit.sum()))
        near |= hit
    return [p for p, n in zip(paths, near) if not n], counts


def nearest(scores):
    g = np.clip(np.rint(scores), 0, 4)
    return g.astype(int), np.abs(scores - g)


def teacher_scores(grader, split, rows, index_rows=None):
    arrays = [cached(split, rows, grader.size)]
    idx = [(0, j) for j in (index_rows if index_rows is not None else range(len(rows)))]
    outs = [predict(m, arrays, idx, grader.device, 32)[:, 0].numpy() for m in grader.models]
    return np.mean(outs, 0)


def inner_holdout_scores(grader):
    """App-grader scores on the fine-tuner's inner hold-out, built exactly as finetune_mixed builds it (same pool order,
    strata and split seed). Returns (scores, labels, dataset index into POOL)."""
    pool = [data.load_split(s)[0] for s in POOL]
    y = np.concatenate([[int(r["DR_grade"]) for r in rows] for rows in pool])
    source = np.concatenate([[k] * len(rows) for k, rows in enumerate(pool)])
    strata = source * 5 + y
    _, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    offsets = np.cumsum([0] + [len(r) for r in pool])
    scores, labels, ds = [], [], []
    for k, split in enumerate(POOL):
        local = [i - offsets[k] for i in inner_va if source[i] == k]
        scores.append(teacher_scores(grader, split, pool[k], local))
        labels.append(y[offsets[k] + np.array(local)])
        ds.append(np.full(len(local), k))
    return np.concatenate(scores), np.concatenate(labels), np.concatenate(ds)


def main():
    app = json.loads((ROOT / "configs/app/app.json").read_text())
    spec = app["grader"]
    if not spec.startswith("finetune:"):
        raise SystemExit(f"teacher must be a fine-tuned regression grader, got {spec}")
    grader = FinetunedGrader(sorted(glob.glob(str(ROOT / spec.removeprefix("finetune:")))))
    if grader.head != "reg" or grader.prep != "plain":
        raise SystemExit("teacher must be a plain-preprocessing regression grader")

    s_in, y_in, _ = inner_holdout_scores(grader)
    g_in, dist_in = nearest(s_in)
    grid = {}
    for d in D_GRID:
        keep = dist_in <= d
        grid[d] = dict(retained=int(keep.sum()), retained_fraction=float(keep.mean()), accuracy=float((g_in[keep] == y_in[keep]).mean()) if keep.any() else None)
    ok = [d for d in D_GRID if grid[d]["accuracy"] is not None and grid[d]["accuracy"] >= MIN_ACC]
    decision = dict(adr="ADR-018", teacher=spec, inner_holdout_n=int(len(y_in)), d_grid=grid)
    if not ok:
        decision["outcome"] = "no d reaches 0.90 accuracy on the inner hold-out; no pseudo-labels"
        (ROOT / "queue/decisions/pseudo_label_prep.json").write_text(json.dumps(decision, indent=2))
        print("RESULT: ADR-018 stopped: no d reaches 0.90 inner accuracy", flush=True)
        raise SystemExit(2)
    d = max(ok)

    test_paths = sorted(Path(p).relative_to(ROOT).as_posix() for p in glob.glob(str(ROOT / "data/raw/APTOS2019/test_images/*.png")))
    clean, leaks = leak_check(test_paths)
    rows = [dict(id_code=Path(p).stem, filepath=p, content_hash=Path(p).stem, DR_grade="") for p in clean]
    scores = teacher_scores(grader, "aptos_test_unlabelled", rows)
    g, dist = nearest(scores)
    keep = dist <= d
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_code", "filepath", "DR_grade", "content_hash", "teacher_score"])
        w.writeheader()
        for r, s, gg, k in zip(rows, scores, g, keep):
            if k:
                w.writerow(dict(id_code=r["id_code"], filepath=r["filepath"], DR_grade=int(gg), content_hash=r["content_hash"], teacher_score=round(float(s), 4)))
    decision.update(d=d, leak_check=leaks, test_images=len(test_paths), after_leak_check=len(clean), pseudo_labelled=int(keep.sum()),
                    pseudo_grade_counts={int(k): int(v) for k, v in zip(*np.unique(g[keep], return_counts=True))}, output=OUT.relative_to(ROOT).as_posix())
    (ROOT / "queue/decisions").mkdir(parents=True, exist_ok=True)
    (ROOT / "queue/decisions/pseudo_label_prep.json").write_text(json.dumps(decision, indent=2))
    print(f"RESULT: ADR-018 d={d} (inner accuracy {grid[d]['accuracy']:.3f}); {len(test_paths) - len(clean)} leak-dropped; "
          f"{int(keep.sum())}/{len(clean)} pseudo-labelled {decision['pseudo_grade_counts']}", flush=True)


if __name__ == "__main__":
    torch.backends.cudnn.benchmark = True
    main()
