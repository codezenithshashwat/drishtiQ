"""Full fine-tuning of a timm grader on IDRiD dev-train only.

Early stopping and (for the regression head) QWK-optimised thresholds use an inner stratified 20% hold-out of
dev-train; the frozen validation splits are never touched here.

    .venv\\Scripts\\python src\\train\\finetune_grader.py --arch convnext_tiny.fb_in1k --head ce --size 384 --seed 17
"""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import minimize
from sklearn.metrics import cohen_kappa_score, f1_score
from sklearn.model_selection import StratifiedShuffleSplit
from torchvision.transforms import v2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference.finetuned import build, regression_to_grade  # noqa: E402
from inference.pipeline import MEAN, STD, default_device  # noqa: E402
from inference.preprocess import PREPROCESSORS  # noqa: E402

OUT = ROOT / "models/checkpoints/phase1/graders"
CACHE = ROOT / "results/cache"


def cached_images(rows, prep, size):
    key = hashlib.sha256(("|".join(r["content_hash"] for r in rows) + f"{prep}{size}").encode()).hexdigest()[:12]
    path = CACHE / f"{prep}{size}_{key}.npy"
    if path.exists():
        return np.load(path)
    arr = np.stack([PREPROCESSORS[prep](data.load_image(r["filepath"]), size) for r in rows])
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return arr


def augmenter(size):
    # Fundus photographs have no canonical orientation: full rotation and both flips are label-preserving.
    return v2.Compose([
        v2.RandomHorizontalFlip(), v2.RandomVerticalFlip(),
        v2.RandomAffine(degrees=180, scale=(0.95, 1.05), fill=0.5),
        v2.ColorJitter(brightness=0.1, contrast=0.1),
    ])


def to_batch(arr, idx, device, aug=None):
    x = torch.from_numpy(arr[idx]).to(device).permute(0, 3, 1, 2).float() / 255
    if aug is not None:
        x = torch.stack([aug(img) for img in x])
    mean = torch.tensor(MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(STD, device=device).view(1, 3, 1, 1)
    return (x - mean) / std


def fit_thresholds(scores, y):
    """Thresholds for a regression head that maximise QWK (Nelder-Mead from the natural 0.5 cut points)."""
    def loss(t):
        t = np.sort(t)
        return -cohen_kappa_score(y, [regression_to_grade(s, t) for s in scores], weights="quadratic")
    res = minimize(loss, x0=[0.5, 1.5, 2.5, 3.5], method="Nelder-Mead", options=dict(maxiter=400, xatol=1e-3, fatol=1e-4))
    return sorted(float(v) for v in res.x)


def evaluate(model, arr, idx, y, head, device, thresholds=(0.5, 1.5, 2.5, 3.5), micro=16):
    model.eval()
    outs = []
    with torch.no_grad(), torch.autocast(device, enabled=device == "cuda"):
        for i in range(0, len(idx), micro):
            outs.append(model(to_batch(arr, idx[i:i + micro], device)).float().cpu())
    out = torch.cat(outs)
    if head == "ce":
        pred = out.argmax(1).numpy()
        scores = None
    else:
        scores = out[:, 0].numpy()
        pred = np.array([regression_to_grade(s, thresholds) for s in scores])
    return (cohen_kappa_score(y, pred, labels=range(5), weights="quadratic"),
            f1_score(y, pred, labels=range(5), average="macro", zero_division=0), scores)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", required=True)
    ap.add_argument("--head", choices=["ce", "reg"], required=True)
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--patience", type=int, default=10)
    ap.add_argument("--micro", type=int, default=8)
    ap.add_argument("--effective", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--prep", default="ben_graham")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--freeze-bn", action="store_true", help="keep BatchNorm running statistics fixed (small micro-batches)")
    args = ap.parse_args()
    device = default_device()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)

    tag = f"{args.arch.split('.')[0]}_{args.head}_{args.prep}{args.size}{'_bnfrozen' if args.freeze_bn else ''}_{args.version}_s{args.seed}"
    path = OUT / f"{tag}.pt"
    if path.exists():
        raise SystemExit(f"{path.name} exists; checkpoints are never overwritten")
    OUT.mkdir(parents=True, exist_ok=True)

    rows, split_sha = data.load_split("idrid_grading_devtrain")
    y = np.array([int(r["DR_grade"]) for r in rows])
    arr = cached_images(rows, args.prep, args.size)
    inner_tr, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(y, y))

    model = build(args.arch, args.head, pretrained=True).to(device)
    model.set_grad_checkpointing(True)
    head_params = list(model.get_classifier().parameters())
    head_ids = {id(p) for p in head_params}
    opt = torch.optim.AdamW([{"params": [p for p in model.parameters() if id(p) not in head_ids], "lr": args.lr},
                             {"params": head_params, "lr": args.lr * 5}], weight_decay=0.05)
    accum = max(1, args.effective // args.micro)
    steps_per_epoch = math.ceil(len(inner_tr) / args.effective)
    total, warm = args.epochs * steps_per_epoch, 2 * steps_per_epoch
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, total - warm))))
    scaler = torch.amp.GradScaler(device, enabled=device == "cuda")
    aug = augmenter(args.size)
    target = torch.tensor(y, device=device)
    best, best_epoch, history, start = (-2, -2), -1, [], time.perf_counter()
    torch.cuda.reset_peak_memory_stats() if device == "cuda" else None
    for epoch in range(args.epochs):
        model.train()
        if args.freeze_bn:
            for m in model.modules():
                if isinstance(m, torch.nn.modules.batchnorm._BatchNorm):
                    m.eval()
        order = rng.permutation(inner_tr)
        losses = []
        for step_i, i in enumerate(range(0, len(order), args.micro)):
            idx = order[i:i + args.micro]
            with torch.autocast(device, enabled=device == "cuda"):
                out = model(to_batch(arr, idx, device, aug)).float()
            loss = (torch.nn.functional.cross_entropy(out, target[idx], label_smoothing=0.05) if args.head == "ce"
                    else torch.nn.functional.smooth_l1_loss(out[:, 0], target[idx].float()))
            scaler.scale(loss / accum).backward()
            losses.append(loss.item())
            if (step_i + 1) % accum == 0 or i + args.micro >= len(order):
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
        qwk, f1, _ = evaluate(model, arr, inner_va, y[inner_va], args.head, device)
        history.append(dict(epoch=epoch, loss=float(np.mean(losses)), inner_qwk=qwk, inner_macro_f1=f1))
        print(f"{tag} epoch {epoch + 1}: loss {np.mean(losses):.4f} inner QWK {qwk:.3f} F1 {f1:.3f}", flush=True)
        if (qwk, f1) > best:
            best, best_epoch = (qwk, f1), epoch
            torch.save(model.state_dict(), path)
        elif epoch - best_epoch >= args.patience:
            break

    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    thresholds = [0.5, 1.5, 2.5, 3.5]
    if args.head == "reg":
        _, _, scores = evaluate(model, arr, inner_va, y[inner_va], args.head, device)
        thresholds = fit_thresholds(scores, y[inner_va])
    qwk_t, f1_t, _ = evaluate(model, arr, inner_va, y[inner_va], args.head, device, thresholds)
    cfg = dict(arch=args.arch, head=args.head, size=args.size, preprocessing=args.prep, seed=args.seed, thresholds=thresholds,
               description=f"Fine-tuned {args.arch} @{args.size}, {args.head} head, {args.prep}",
               train_data=f"IDRiD grading dev-train {len(rows)} (inner 80/20: early stopping{' + thresholds' if args.head == 'reg' else ''})",
               eval_overlap="no", split_sha256=split_sha, best_epoch=best_epoch, inner_qwk=qwk_t, inner_macro_f1=f1_t,
               train_seconds=time.perf_counter() - start, peak_vram_mib=torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else None,
               hyper=dict(epochs=args.epochs, patience=args.patience, micro=args.micro, effective=args.effective, lr=args.lr,
                          weight_decay=0.05, label_smoothing=0.05 if args.head == "ce" else None, loss="CE" if args.head == "ce" else "SmoothL1",
                          augmentation="hflip, vflip, rotate 180, scale 0.95-1.05, brightness/contrast 0.1", amp=True, grad_checkpointing=True,
                          freeze_bn=args.freeze_bn),
               history=history)
    path.with_suffix(".json").write_text(json.dumps(cfg, indent=2))
    print(json.dumps({k: cfg[k] for k in ["best_epoch", "inner_qwk", "inner_macro_f1", "thresholds", "train_seconds", "peak_vram_mib"]}))


if __name__ == "__main__":
    main()
