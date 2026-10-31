"""Train linear heads on frozen ImageNet ConvNeXt-Tiny @224 features using the dev-train split only.

Same recipe as the model-selection study (AdamW lr .01 wd .01, batch 64, <=60 epochs, patience 12,
feature standardisation with std floor .1, checkpoint on macro-F1 then QWK), but early stopping uses an
inner stratified 80/20 split of dev-train, so the frozen validation split is never seen.

    .venv\\Scripts\\python src\\train\\frozen_head.py --seeds 17 29 41
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
from inference import convnext_backbone, default_device, letterbox, to_tensor  # noqa: E402

OUT = ROOT / "models/checkpoints/phase1"
CACHE = ROOT / "results/cache"


@torch.no_grad()
def devtrain_features(rows, device):
    keys = "|".join(r["content_hash"] for r in rows)
    cache = CACHE / f"convnext224_fp32_{data.hashlib.sha256(keys.encode()).hexdigest()[:12]}.npy"
    if cache.exists():
        return np.load(cache)
    backbone = convnext_backbone(device)
    feats = np.stack([backbone(to_tensor(letterbox(data.load_image(r["filepath"]), 224)[0], device))[0].cpu().numpy() for r in rows])
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(cache, feats)
    return feats


def score(y, prob):
    pred = prob.argmax(1)
    return f1_score(y, pred, labels=range(5), average="macro", zero_division=0), cohen_kappa_score(y, pred, labels=range(5), weights="quadratic")


def train_head(x, y, inner_tr, inner_va, seed, device):
    torch.manual_seed(seed)
    np.random.seed(seed)
    mean, std = x[inner_tr].mean(0), x[inner_tr].std(0).clip(0.1)
    z = torch.tensor((x - mean) / std, device=device)
    t = torch.tensor(y, device=device)
    head = torch.nn.Linear(x.shape[1], 5).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=0.01, weight_decay=0.01)
    best, state, patience, history = (-1, -1), None, 0, []
    for epoch in range(60):
        head.train()
        for ix in np.array_split(np.random.permutation(inner_tr), max(1, math.ceil(len(inner_tr) / 64))):
            opt.zero_grad()
            torch.nn.functional.cross_entropy(head(z[ix]), t[ix]).backward()
            opt.step()
        head.eval()
        with torch.no_grad():
            f1, qwk = score(y[inner_va], head(z[inner_va]).softmax(1).cpu().numpy())
        history.append(dict(epoch=epoch, inner_macro_f1=f1, inner_qwk=qwk))
        if (f1, qwk) > best:
            best, state, patience = (f1, qwk), {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 12:
                break
    return state, mean, std, best, history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 41])
    ap.add_argument("--version", default="v1")
    args = ap.parse_args()
    device = default_device()
    rows, split_sha = data.load_split("idrid_grading_devtrain")
    y = np.array([int(r["DR_grade"]) for r in rows])
    x = devtrain_features(rows, device)
    inner_tr, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(y, y))
    OUT.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        path = OUT / f"frozen_convnext224_devtrain_{args.version}_s{seed}.pt"
        if path.exists():
            raise SystemExit(f"{path.name} exists; checkpoints are never overwritten, pass a new --version")
        state, mean, std, best, history = train_head(x, y, inner_tr, inner_va, seed, device)
        torch.save({"head": state, "feature_mean": torch.tensor(mean), "feature_std": torch.tensor(std)}, path)
        path.with_suffix(".json").write_text(json.dumps(dict(
            description="Frozen ConvNeXt-T @224 + linear head(s), trained on dev-train only",
            train_data=f"IDRiD grading dev-train {len(rows)} (inner 80/20 for early stopping)",
            eval_overlap="no", split_sha256=split_sha, seed=seed, inner_best_macro_f1=best[0], inner_best_qwk=best[1],
            epochs_run=len(history), history=history), indent=2))
        print(f"{path.name}: inner macro-F1 {best[0]:.3f} QWK {best[1]:.3f} ({len(history)} epochs)")


if __name__ == "__main__":
    main()
