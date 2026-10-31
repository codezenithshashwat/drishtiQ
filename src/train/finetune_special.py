"""Stage specialists (ADR-028) and the CORN ordinal grader (ADR-029), on the same pool, cache and inner split as
finetune_mixed.py (the inner hold-out is identical, so thresholds fitted here never touch validation data).

    .venv\\Scripts\\python src\\train\\finetune_special.py --task stage01 --size 768   # S2: grade 0 vs 1 (grades <= 1 only)
    .venv\\Scripts\\python src\\train\\finetune_special.py --task stage34 --size 512   # S3: grade 3 vs 4 (grades >= 3, class 4 oversampled)
    .venv\\Scripts\\python src\\train\\finetune_special.py --task corn --size 384 --init <reg384 s17 .pt>  # S4

Per-epoch resume checkpoints; the best epoch by inner AUROC (specialists) or inner QWK (CORN) is kept. Specialist
thresholds (S2: 90% specificity for grade 0; S3: max balanced accuracy) are fitted on the inner hold-out.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import cohen_kappa_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
from eval import data  # noqa: E402
from finetune_mixed import ARCH, POOL, cached, param_groups, to_input  # noqa: E402
from inference.finetuned import build, corn_score, regression_to_grade  # noqa: E402
from inference.pipeline import default_device  # noqa: E402

SPEC_OUT = ROOT / "models/checkpoints/phase2/specialists"
GRADER_OUT = ROOT / "models/checkpoints/phase2/graders"


def corn_loss(logits, y):
    """CORN: task k is trained on samples with y >= k, target y > k (conditional ordinal training)."""
    losses = []
    for k in range(4):
        m = y >= k
        if m.any():
            losses.append(F.binary_cross_entropy_with_logits(logits[m, k], (y[m] > k).float()))
    return torch.stack(losses).mean()


@torch.no_grad()
def outputs(model, arrays, index, device, micro=32):
    model.eval()
    out = []
    with torch.autocast(device, enabled=device == "cuda"):
        for i in range(0, len(index), micro):
            batch = np.stack([arrays[s][j] for s, j in index[i:i + micro]])
            out.append(model(to_input(batch, device, False)).float().cpu())
    return torch.cat(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["stage01", "stage34", "corn"], required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--micro", type=int, default=8)
    ap.add_argument("--effective", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--init", help="warm start: backbone weights from this checkpoint (head re-initialised)")
    args = ap.parse_args()
    device = default_device()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    head = "corn" if args.task == "corn" else "bin"
    out_dir = GRADER_OUT if args.task == "corn" else SPEC_OUT
    tag = f"convnext_tiny_{args.task}_plain{args.size}_v1_s{args.seed}"
    path, resume = out_dir / f"{tag}.pt", out_dir / f"{tag}.resume.pt"
    if path.with_suffix(".json").exists():
        raise SystemExit(f"{path.name} already finished; checkpoints are never overwritten")
    out_dir.mkdir(parents=True, exist_ok=True)

    arrays, index, y, source = [], [], [], []
    for k, split in enumerate(POOL):
        rows, _ = data.load_split(split)
        arrays.append(cached(split, rows, args.size))
        index += [(k, j) for j in range(len(rows))]
        y += [int(r["DR_grade"]) for r in rows]
        source += [k] * len(rows)
    y, source = np.array(y), np.array(source)
    strata = source * 5 + y
    inner_tr, inner_va = next(StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=data.SPLIT_SEED).split(strata, strata))
    if args.task == "stage01":
        keep = y <= 1
        target = (y == 1).astype(np.float32)
    elif args.task == "stage34":
        keep = y >= 3
        target = (y == 4).astype(np.float32)
    else:
        keep = np.ones(len(y), bool)
        target = y.astype(np.float32)
    inner_tr, inner_va = inner_tr[keep[inner_tr]], inner_va[keep[inner_va]]

    w = 1.0 / np.bincount(source[inner_tr], minlength=len(POOL))[source]  # dataset-balanced, as finetune_mixed
    cls = target.astype(int) if head == "bin" else y
    counts = np.zeros((len(POOL), int(cls.max()) + 1))
    np.add.at(counts, (source[inner_tr], cls[inner_tr]), 1)
    power = 1.0 if args.task == "stage34" else 0.5  # S3: class 4 oversampled to balance; others: sqrt weights
    w = w / np.maximum(counts[source, cls], 1) ** power
    p_tr = w[inner_tr] / w[inner_tr].sum()

    model = build(ARCH, head, pretrained=args.init is None).to(device)
    if args.init:
        state = torch.load(ROOT / args.init, map_location="cpu", weights_only=True)
        missing = model.load_state_dict({k: v for k, v in state.items() if not k.startswith("head.fc")}, strict=False)
        print(f"warm start from {args.init}; re-initialised: {missing.missing_keys}", flush=True)
    model.set_grad_checkpointing(True)
    opt = torch.optim.AdamW(param_groups(model, args.lr), weight_decay=0.05)
    accum = max(1, args.effective // args.micro)
    steps = math.ceil(len(inner_tr) / args.effective)
    total, warm = args.epochs * steps, steps
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, total - warm))))
    scaler = torch.amp.GradScaler(device, enabled=device == "cuda")
    t_all = torch.tensor(target, device=device)
    start_epoch, best, best_epoch, history = 0, -1.0, -1, []
    if resume.exists():
        st = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"]); scaler.load_state_dict(st["scaler"])
        start_epoch, best, best_epoch, history = st["epoch"] + 1, st["best"], st["best_epoch"], st["history"]
        rng = np.random.default_rng(args.seed + start_epoch)
        print(f"resumed at epoch {start_epoch}", flush=True)
    va_index = [index[i] for i in inner_va]
    t0 = time.perf_counter()
    for epoch in range(start_epoch, args.epochs):
        model.train()
        draw = rng.choice(inner_tr, size=len(inner_tr), replace=True, p=p_tr)
        losses, te = [], time.perf_counter()
        for step_i, i in enumerate(range(0, len(draw), args.micro)):
            ids = draw[i:i + args.micro]
            batch = np.stack([arrays[source[j]][index[j][1]] for j in ids])
            with torch.autocast(device, enabled=device == "cuda"):
                out = model(to_input(batch, device, True)).float()
            loss = corn_loss(out, t_all[ids].long()) if head == "corn" else F.binary_cross_entropy_with_logits(out[:, 0], t_all[ids])
            scaler.scale(loss / accum).backward()
            losses.append(loss.item())
            if (step_i + 1) % accum == 0 or i + args.micro >= len(draw):
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
        out = outputs(model, arrays, va_index, device)
        if head == "corn":
            pred = np.array([regression_to_grade(float(s), (0.5, 1.5, 2.5, 3.5)) for s in corn_score(out)])
            metric = cohen_kappa_score(y[inner_va], pred, weights="quadratic")
        else:
            metric = roc_auc_score(target[inner_va], torch.sigmoid(out[:, 0]).numpy())
        history.append(dict(epoch=epoch, loss=float(np.mean(losses)), inner_metric=float(metric), seconds=time.perf_counter() - te))
        print(f"{tag} epoch {epoch + 1}: loss {np.mean(losses):.4f} inner {'QWK' if head == 'corn' else 'AUROC'} {metric:.3f} ({time.perf_counter() - te:.0f}s)", flush=True)
        if metric > best:
            best, best_epoch = float(metric), epoch
            torch.save(model.state_dict(), path)
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), scaler=scaler.state_dict(), epoch=epoch,
                        best=best, best_epoch=best_epoch, history=history), resume)
        if epoch - best_epoch >= args.patience:
            break

    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    out = outputs(model, arrays, va_index, device)
    cfg = dict(arch=ARCH, head=head, size=args.size, preprocessing="plain", seed=args.seed, task=args.task, best_epoch=best_epoch,
               inner_metric=best, history=history, train_seconds=time.perf_counter() - t0,
               train_data=f"mixed pool training side ({len(inner_tr)} images, task {args.task})", eval_overlap="no")
    if head == "corn":
        cfg.update(thresholds=[0.5, 1.5, 2.5, 3.5], description=f"Fine-tuned ConvNeXt-T @{args.size}, CORN ordinal head (ADR-029), warm start {args.init}")
    else:
        p = torch.sigmoid(out[:, 0]).numpy()
        t = target[inner_va]
        if args.task == "stage01":
            thr = float(np.quantile(p[t == 0], 0.90))  # 90% specificity for grade 0 on the inner hold-out
            cfg.update(low_stage=0, high_stage=1)
        else:
            cands = np.unique(p)
            thr = float(max(cands, key=lambda c: 0.5 * ((p[t == 1] >= c).mean() + (p[t == 0] < c).mean())))
            cfg.update(low_stage=3, high_stage=4)
        cfg.update(threshold=thr, description=f"ConvNeXt-T @{args.size} specialist {args.task} (ADR-028)",
                   inner_sensitivity=float((p[t == 1] >= thr).mean()), inner_specificity=float((p[t == 0] < thr).mean()))
    path.with_suffix(".json").write_text(json.dumps(cfg, indent=2))
    resume.unlink(missing_ok=True)
    print(f"RESULT: {tag} best epoch {best_epoch + 1}, inner {'QWK' if head == 'corn' else 'AUROC'} {best:.3f}"
          + (f", threshold {cfg['threshold']:.3f} (inner sens {cfg['inner_sensitivity']:.2f}, spec {cfg['inner_specificity']:.2f})" if head == "bin" else ""), flush=True)


if __name__ == "__main__":
    main()
