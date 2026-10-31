"""Full fine-tuning of ConvNeXt-T on the mixed training pool (IDRiD dev-train + APTOS-train + MMRDR-CFP).

- Input: FOV crop + square resize ("plain" preprocessing), cached as memory-mapped uint8 arrays.
- Inner 20% hold-out stratified by dataset x grade: early stopping and (regression head) QWK-optimised thresholds.
  The validation splits (IDRiD-val, APTOS-val) are never read here.
- Sampling: each epoch draws len(inner-train) samples with replacement; weights = dataset balance (optional) x
  class weight (optional, inverse square-root of grade frequency within each dataset).
- Augmentation on GPU per batch: h/v flips, rotation U(-180, 180), scale U(0.95, 1.05), brightness/contrast +-10%.
- Discriminative LR: ConvNeXt stem/stage multipliers 0.25/0.25/0.4/0.6/0.8, head 5x; 1-epoch warmup + cosine; AdamW.
- AMP + gradient checkpointing; resumable (last-epoch state saved every epoch).

    .venv\\Scripts\\python src\\train\\finetune_mixed.py --head reg --size 384 --seed 17
"""
import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from sklearn.metrics import cohen_kappa_score, f1_score
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference.finetuned import build, regression_to_grade  # noqa: E402
from inference.pipeline import MEAN, STD, default_device  # noqa: E402
from inference.preprocess import plain  # noqa: E402
from train.finetune_grader import fit_thresholds  # noqa: E402

OUT = ROOT / "models/checkpoints/phase2/graders"
CACHE = ROOT / "results/cache"
POOL = ["idrid_grading_devtrain", "aptos_train", "mmrdr_train"]
SHORT = {"idrid_grading_devtrain": "idrid", "aptos_train": "aptos", "mmrdr_train": "mmrdr"}
ARCH = "convnext_tiny.fb_in1k"


def cached(split, rows, size):
    key = hashlib.sha256("|".join(r["content_hash"] for r in rows).encode()).hexdigest()[:10]
    path = CACHE / f"plain{size}_{split}_{key}.npy"
    if path.exists():
        return np.load(path, mmap_mode="r")
    tmp = path.with_suffix(".partial.npy")
    arr = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.uint8, shape=(len(rows), size, size, 3))

    def work(i):
        with Image.open(ROOT / rows[i]["filepath"]) as im:
            arr[i] = plain(ImageOps.exif_transpose(im).convert("RGB"), size)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(work, range(len(rows))))
    arr.flush()
    del arr
    tmp.replace(path)
    return np.load(path, mmap_mode="r")


def gpu_augment(x):
    """x: (B,3,H,W) float in [0,1] on GPU."""
    b = x.shape[0]
    flip_h = torch.rand(b, device=x.device) < 0.5
    flip_v = torch.rand(b, device=x.device) < 0.5
    x = torch.where(flip_h[:, None, None, None], x.flip(-1), x)
    x = torch.where(flip_v[:, None, None, None], x.flip(-2), x)
    angle = (torch.rand(b, device=x.device) * 2 - 1) * math.pi
    scale = 1 / (0.95 + 0.1 * torch.rand(b, device=x.device))
    cos, sin = torch.cos(angle) * scale, torch.sin(angle) * scale
    theta = torch.stack([torch.stack([cos, -sin, torch.zeros_like(cos)], 1), torch.stack([sin, cos, torch.zeros_like(cos)], 1)], 1)
    x = F.grid_sample(x, F.affine_grid(theta, x.shape, align_corners=False), align_corners=False, padding_mode="zeros")
    bright = 1 + (torch.rand(b, 1, 1, 1, device=x.device) * 2 - 1) * 0.1
    contrast = 1 + (torch.rand(b, 1, 1, 1, device=x.device) * 2 - 1) * 0.1
    mean = x.mean((1, 2, 3), keepdim=True)
    return ((x - mean) * contrast + mean) * bright


def to_input(batch_uint8, device, augment):
    x = torch.from_numpy(np.ascontiguousarray(batch_uint8)).to(device, non_blocking=True).permute(0, 3, 1, 2).float() / 255
    if augment:
        x = gpu_augment(x).clamp(0, 1)
    return (x - torch.tensor(MEAN, device=device).view(1, 3, 1, 1)) / torch.tensor(STD, device=device).view(1, 3, 1, 1)


def param_groups(model, lr, head_mult=5.0):
    mults = {"stem": 0.25, "stages.0": 0.25, "stages.1": 0.4, "stages.2": 0.6, "stages.3": 0.8}
    groups = {}
    for name, p in model.named_parameters():
        m = next((v for k, v in mults.items() if name.startswith(k)), head_mult)
        groups.setdefault(m, []).append(p)
    return [{"params": ps, "lr": lr * m, "lr_mult": m} for m, ps in groups.items()]


def predict(model, arrays, index, device, micro):
    out = []
    model.eval()
    with torch.no_grad(), torch.autocast(device, enabled=device == "cuda"):
        for i in range(0, len(index), micro):
            batch = np.stack([arrays[s][j] for s, j in index[i:i + micro]])
            out.append(model(to_input(batch, device, False)).float().cpu())
    return torch.cat(out)


def score(y, out, head, thresholds=(0.5, 1.5, 2.5, 3.5)):
    pred = out.argmax(1).numpy() if head == "ce" else np.array([regression_to_grade(s, thresholds) for s in out[:, 0].numpy()])
    return cohen_kappa_score(y, pred, labels=range(5), weights="quadratic"), f1_score(y, pred, labels=range(5), average="macro", zero_division=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", choices=["ce", "reg", "regbin"], required=True)  # regbin: reg + separate referable logit (ADR-041 4c)
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--micro", type=int, default=16)
    ap.add_argument("--effective", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--balance", choices=["none", "dataset"], default="dataset")
    ap.add_argument("--class-weight", choices=["none", "sqrt"], default="sqrt")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--pseudo", help="CSV of pseudo-labelled APTOS images (ADR-018); added to the training side only")
    ap.add_argument("--extra-split", help="another labelled split (e.g. eyepacs_train, ADR-037): training side only, own dataset share")
    args = ap.parse_args()
    device = default_device()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)

    tag = f"convnext_tiny_mixed_{args.head}_plain{args.size}_{args.balance}bal_{args.class_weight}cw_{args.version}_s{args.seed}"
    path, resume = OUT / f"{tag}.pt", OUT / f"{tag}.resume.pt"
    if path.with_suffix(".json").exists():
        raise SystemExit(f"{path.name} already finished; checkpoints are never overwritten")
    OUT.mkdir(parents=True, exist_ok=True)

    arrays, index, y, source, shas = [], [], [], [], {}
    for k, split in enumerate(POOL):
        rows, shas[split] = data.load_split(split)
        arrays.append(cached(split, rows, args.size))
        index += [(k, j) for j in range(len(rows))]
        y += [int(r["DR_grade"]) for r in rows]
        source += [k] * len(rows)
    y, source = np.array(y), np.array(source)
    strata = source * 5 + y
    inner_tr, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    va_index = [index[i] for i in inner_va]
    if args.pseudo:  # appended after the inner split, so the hold-out is identical to the teacher's
        pl = data.read_csv(ROOT / args.pseudo)
        arrays.append(cached("aptos_pseudo", pl, args.size))
        start = len(y)
        index += [(len(arrays) - 1, j) for j in range(len(pl))]
        y = np.concatenate([y, [int(r["DR_grade"]) for r in pl]])
        source = np.concatenate([source, np.full(len(pl), POOL.index("aptos_train"))])  # pseudo rows share APTOS's sampling share
        inner_tr = np.concatenate([inner_tr, np.arange(start, len(y))])

    n_sources = len(POOL)
    if args.extra_split:  # appended after the inner split, so the inner hold-out (and its thresholds) is unchanged
        ex, shas[args.extra_split] = data.load_split(args.extra_split)
        arrays.append(cached(args.extra_split, ex, args.size))
        start = len(y)
        index += [(len(arrays) - 1, j) for j in range(len(ex))]
        y = np.concatenate([y, [int(r["DR_grade"]) for r in ex]])
        source = np.concatenate([source, np.full(len(ex), n_sources)])
        inner_tr = np.concatenate([inner_tr, np.arange(start, len(y))])
        n_sources += 1

    w = np.ones(len(y))
    if args.balance == "dataset":
        w /= np.bincount(source[inner_tr], minlength=n_sources)[source]
    if args.class_weight == "sqrt":
        counts = np.zeros((n_sources, 5))
        np.add.at(counts, (source[inner_tr], y[inner_tr]), 1)
        w /= np.sqrt(np.maximum(counts[source, y], 1))
    p_tr = w[inner_tr] / w[inner_tr].sum()

    model = build(ARCH, args.head, pretrained=True).to(device)
    model.set_grad_checkpointing(True)
    opt = torch.optim.AdamW(param_groups(model, args.lr), weight_decay=0.05)
    accum = max(1, args.effective // args.micro)
    steps = math.ceil(len(inner_tr) / args.effective)
    total, warm = args.epochs * steps, steps
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, total - warm))))
    scaler = torch.amp.GradScaler(device, enabled=device == "cuda")
    target = torch.tensor(y, device=device)
    start_epoch, best, best_epoch, history = 0, (-2.0, -2.0), -1, []
    if resume.exists():
        st = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"]); scaler.load_state_dict(st["scaler"])
        start_epoch, best, best_epoch, history = st["epoch"] + 1, tuple(st["best"]), st["best_epoch"], st["history"]
        rng = np.random.default_rng(args.seed + start_epoch)
        print(f"resumed at epoch {start_epoch}", flush=True)
    t0 = time.perf_counter()
    for epoch in range(start_epoch, args.epochs):
        model.train()
        draw = rng.choice(inner_tr, size=len(inner_tr), replace=True, p=p_tr)
        losses, te = [], time.perf_counter()
        for step_i, i in enumerate(range(0, len(draw), args.micro)):
            ids = draw[i:i + args.micro]
            batch = np.stack([arrays[index[j][0]][index[j][1]] for j in ids])
            with torch.autocast(device, enabled=device == "cuda"):
                out = model(to_input(batch, device, True)).float()
            loss = (F.cross_entropy(out, target[ids], label_smoothing=0.05) if args.head == "ce"
                    else F.smooth_l1_loss(out[:, 0], target[ids].float()))
            if args.head == "regbin":  # equal weight, fixed before training (ADR-041)
                loss = loss + F.binary_cross_entropy_with_logits(out[:, 1], (target[ids] >= 2).float())
            scaler.scale(loss / accum).backward()
            losses.append(loss.item())
            if (step_i + 1) % accum == 0 or i + args.micro >= len(draw):
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
        out = predict(model, arrays, va_index, device, args.micro * 2)
        qwk, f1 = score(y[inner_va], out, args.head)
        per_ds = {SHORT[s]: round(score(y[inner_va][source[inner_va] == k], out[torch.from_numpy(source[inner_va] == k)], args.head)[0], 4)
                  for k, s in enumerate(POOL)}
        history.append(dict(epoch=epoch, loss=float(np.mean(losses)), inner_qwk=qwk, inner_macro_f1=f1, inner_qwk_by_dataset=per_ds,
                            epoch_seconds=time.perf_counter() - te))
        print(f"{tag} epoch {epoch + 1}: loss {np.mean(losses):.4f} inner QWK {qwk:.3f} F1 {f1:.3f} {per_ds} ({time.perf_counter() - te:.0f}s)", flush=True)
        if (qwk, f1) > best:
            best, best_epoch = (qwk, f1), epoch
            torch.save(model.state_dict(), path)
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), scaler=scaler.state_dict(), epoch=epoch,
                        best=list(best), best_epoch=best_epoch, history=history), resume)
        if epoch - best_epoch >= args.patience:
            break

    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    out = predict(model, arrays, va_index, device, args.micro * 2)
    thresholds = [0.5, 1.5, 2.5, 3.5]
    if args.head in ("reg", "regbin"):
        thresholds = fit_thresholds(out[:, 0].numpy(), y[inner_va])
    qwk_t, f1_t = score(y[inner_va], out, args.head, thresholds)
    cfg = dict(arch=ARCH, head=args.head, size=args.size, preprocessing="plain", seed=args.seed, thresholds=thresholds,
               description=f"Fine-tuned ConvNeXt-T @{args.size} on IDRiD+APTOS+MMRDR, {args.head} head, FOV crop",
               train_data=" + ".join(f"{s} ({int((source == k).sum())})" for k, s in enumerate(POOL))
               + (f" incl. {args.pseudo} pseudo-labels in the APTOS share" if args.pseudo else "")
               + f"; inner 80/20 (dataset x grade): early stopping{' + thresholds' if args.head in ('reg', 'regbin') else ''}; "
               f"sampling balance={args.balance}, class weight={args.class_weight}",
               eval_overlap="no", splits_sha256=shas, best_epoch=best_epoch, inner_qwk=qwk_t, inner_macro_f1=f1_t,
               train_seconds=time.perf_counter() - t0, peak_vram_mib=torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else None,
               hyper=vars(args) | dict(lr_multipliers="stem/stage0 0.25, stage1 0.4, stage2 0.6, stage3 0.8, head 5", weight_decay=0.05,
                                        warmup_epochs=1, schedule="cosine", amp=True, grad_checkpointing=True,
                                        augmentation="GPU: h/v flip, rotate U(-180,180), scale U(0.95,1.05), brightness/contrast 10%"),
               history=history)
    path.with_suffix(".json").write_text(json.dumps(cfg, indent=2))
    resume.unlink(missing_ok=True)
    print(json.dumps({k: cfg[k] for k in ["best_epoch", "inner_qwk", "inner_macro_f1", "thresholds", "train_seconds", "peak_vram_mib"]}), flush=True)


if __name__ == "__main__":
    main()
