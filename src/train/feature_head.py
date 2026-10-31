"""Linear-probe graders on frozen backbones (ConvNeXt-T ImageNet vs RETFound CFP) under one protocol.

Same recipe as the frozen-head baseline (AdamW lr .01 wd .01, batch 64, <=60 epochs, patience 12, standardised
features with std floor .1, checkpoint on inner macro-F1 then QWK). Early stopping uses an inner 20% hold-out of the
training splits, stratified by dataset x grade; the validation splits are never seen.

    .venv\\Scripts\\python src\\train\\feature_head.py --backbone retfound_cfp --train idrid_grading_devtrain aptos_train
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import cohen_kappa_score, f1_score
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference.backbones import Backbone, cached_inputs  # noqa: E402
from inference.pipeline import default_device  # noqa: E402

OUT = ROOT / "models/checkpoints/phase2/feathead"
CACHE = ROOT / "results/cache"
SIZE = 224
SHORT = {"idrid_grading_devtrain": "idrid", "aptos_train": "aptos", "mmrdr_train": "mmrdr"}


def features(backbone, split, rows):
    path = CACHE / "features" / f"{backbone.name}_fovcrop{SIZE}_{split}.npy"
    if path.exists():
        return np.load(path)
    arr = cached_inputs(rows, split, SIZE, CACHE)
    feats = np.concatenate([backbone(arr[i:i + 32]).cpu().numpy() for i in range(0, len(arr), 32)])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, feats)
    return feats


def train_head(x, y, inner_tr, inner_va, seed, device, sample_weight=None):
    torch.manual_seed(seed)
    np.random.seed(seed)
    mean, std = x[inner_tr].mean(0), x[inner_tr].std(0).clip(0.1)
    z, t = torch.tensor((x - mean) / std, device=device), torch.tensor(y, device=device)
    w = torch.tensor(sample_weight if sample_weight is not None else np.ones(len(y)), device=device, dtype=torch.float32)
    head = torch.nn.Linear(x.shape[1], 5).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=0.01, weight_decay=0.01)
    best, state, patience, history = (-1, -1), None, 0, []
    for epoch in range(60):
        head.train()
        for ix in np.array_split(np.random.permutation(inner_tr), max(1, math.ceil(len(inner_tr) / 64))):
            opt.zero_grad()
            loss = torch.nn.functional.cross_entropy(head(z[ix]), t[ix], reduction="none")
            (loss * w[ix]).sum().div(w[ix].sum()).backward()
            opt.step()
        head.eval()
        with torch.no_grad():
            pred = head(z[inner_va]).argmax(1).cpu().numpy()
        score = (f1_score(y[inner_va], pred, labels=range(5), average="macro", zero_division=0),
                 cohen_kappa_score(y[inner_va], pred, labels=range(5), weights="quadratic"))
        history.append(dict(epoch=epoch, inner_macro_f1=score[0], inner_qwk=score[1]))
        if score > best:
            best, state, patience = score, {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 12:
                break
    return state, mean, std, best, history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", required=True, choices=["convnext_tiny_in1k", "retfound_cfp", "retfound_cfp_officialpool"])
    ap.add_argument("--train", nargs="+", default=["idrid_grading_devtrain"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 41])
    ap.add_argument("--version", default="v1")
    ap.add_argument("--extract-only", action="store_true", help="also cache features for the validation splits and stop")
    ap.add_argument("--extract", nargs="*", default=[], help="extra splits to cache features for with --extract-only")
    ap.add_argument("--balance", choices=["none", "dataset"], default="none",
                    help="dataset: loss weights so every training dataset contributes equally (natural mix otherwise)")
    args = ap.parse_args()
    device = default_device()
    backbone = Backbone(args.backbone, device)
    if args.extract_only:
        for split in ["idrid_grading_devtrain", "idrid_grading_val", "aptos_train", "aptos_val"] + args.extract:
            rows, _ = data.load_split(split)
            print(split, features(backbone, split, rows).shape, flush=True)
        return

    xs, ys, source, shas = [], [], [], {}
    for k, split in enumerate(args.train):
        rows, shas[split] = data.load_split(split)
        xs.append(features(backbone, split, rows))
        ys.append(np.array([int(r["DR_grade"]) for r in rows]))
        source.append(np.full(len(rows), k))
    x, y, source = np.concatenate(xs), np.concatenate(ys), np.concatenate(source)
    strata = source * 5 + y
    inner_tr, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "+".join(SHORT[s] for s in args.train) + ("_balanced" if args.balance == "dataset" else "")
    weight = None
    if args.balance == "dataset":
        counts = np.bincount(source)
        weight = 1.0 / counts[source]
    for seed in args.seeds:
        path = OUT / f"{args.backbone}_{tag}_{args.version}_s{seed}.pt"
        if path.exists():
            raise SystemExit(f"{path.name} exists; checkpoints are never overwritten")
        state, mean, std, best, history = train_head(x, y, inner_tr, inner_va, seed, device, weight)
        torch.save({"head": state, "feature_mean": torch.tensor(mean), "feature_std": torch.tensor(std)}, path)
        path.with_suffix(".json").write_text(json.dumps(dict(
            backbone=args.backbone, preprocessing=f"fovcrop{SIZE}", seed=seed,
            description=f"Linear probe on frozen {args.backbone} (fovcrop {SIZE}), trained on {tag}",
            train_data=" + ".join(f"{s} ({len(r)})" for s, r in zip(args.train, ys)) + "; inner 80/20 (dataset x grade) for early stopping"
            + ("; dataset-balanced loss weights" if args.balance == "dataset" else "; natural mix"),
            balance=args.balance,
            eval_overlap="no", splits_sha256=shas, inner_best_macro_f1=best[0], inner_best_qwk=best[1], epochs_run=len(history),
            history=history), indent=2))
        print(f"{path.name}: inner macro-F1 {best[0]:.3f} QWK {best[1]:.3f} ({len(history)} epochs)", flush=True)


if __name__ == "__main__":
    main()

