"""A3 lesion segmentation (ADR-014/016): one 4-channel U-Net (ResNet18) on DDR train+valid plus IDRiD dev images.

Folds reuse the v0 CV assignment (results/cache/segcv/folds.json): folds 0-3 split the 40 IDRiD dev-train images,
fold 4 is the frozen 10-image IDRiD-val split. Fold k trains on all 527 DDR train+valid images plus the IDRiD images
not in fold k, then writes out-of-fold maps for fold k. The fold-4 model (DDR + the 40 IDRiD dev-train images) is the
A3 candidate for the app.

Recipe (fixed before any result): FOV crop resized to 1536 px; 512 px patches with centres uniform over the FOV
(natural lesion frequency); each batch 3 IDRiD + 5 DDR patches; flips/rot90; loss = gated BCE + batch soft Dice per
lesion (missing IDRiD masks gated out, empty DDR masks are negatives); AdamW 3e-4, 200-step warm-up, cosine decay,
4,000 steps, AMP. One "epoch" = 500 steps; a resume checkpoint is written after each.

    .venv\\Scripts\\python src\\train\\seg_a3.py --fold 4 [--steps 4000] [--smoke]
"""
import argparse
import json
import math
import os
import queue
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # encoder weights are cached; an unattended run must not need the network
os.environ.setdefault("HF_HUB_CACHE", str(Path(__file__).resolve().parents[2] / "models/pretrained/huggingface/hub"))  # project cache

import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/train"))
from eval import data  # noqa: E402
from inference import default_device  # noqa: E402
from inference.a3_segmenter import TRANSFORM_OF, TRANSFORMS, VARIANTS, A3Segmenter, build  # noqa: E402
from inference.pipeline import MEAN, STD  # noqa: E402
from seg_data import PatchSampler, build_cache  # noqa: E402

OUT = ROOT / "models/checkpoints/phase2/seg_a3"
OOF = ROOT / "results/cache/seg_a3_cv"
SEED = 17
TAG = "unet_r18_fov1536"
STEPS_PER_EPOCH = 500


def pools(fold, smoke):
    ddr, _ = data.load_split("ddr_seg_trainval")
    idrid = data.load_split("idrid_seg_train")[0] + data.load_split("idrid_seg_val")[0]
    fold_of = json.loads((ROOT / "results/cache/segcv/folds.json").read_text())
    if smoke:
        ddr, idrid = ddr[:6], [r for r in idrid if fold_of[r["image_id"]] in (fold, (fold + 1) % 5)][:6]
    train_ids = [i for i, r in enumerate(idrid) if fold_of[r["image_id"]] != fold]
    held = [r for r in idrid if fold_of[r["image_id"]] == fold]
    return ddr, idrid, train_ids, held


def tversky_loss(logits, y, valid, alpha=0.3, beta=0.7):
    """Small-object-aware Tversky loss on the MA channel (ADR-031 MA variant), gated by MA supervision."""
    gate = valid[:, :1, None, None]
    p, t = logits[:, :1].float().sigmoid() * gate, y[:, :1] * gate
    tp, fp, fn = (p * t).sum(), (p * (1 - t)).sum(), ((1 - p) * t).sum()
    return 1 - (tp + 1) / (tp + alpha * fp + beta * fn + 1)


def focal_term(logits, y, valid, lesion, gamma=2.0):
    """Focal loss (gamma 2) on one lesion channel, gated by its supervision (ADR-036 loss upgrade)."""
    k = ["MA", "HE", "EX", "SE"].index(lesion)
    z, t = logits[:, k].float(), y[:, k]
    p = torch.sigmoid(z)
    bce = F.binary_cross_entropy_with_logits(z, t, reduction="none")
    focal = ((1 - torch.where(t > 0.5, p, 1 - p)) ** gamma * bce).mean((1, 2))
    return (focal * valid[:, k]).sum() / valid[:, k].sum().clamp_min(1)


def bce_part(logits, y, valid):
    """The gated BCE term of loss_fn alone (so focal can replace it on one channel)."""
    bce = F.binary_cross_entropy_with_logits(logits.float(), y, reduction="none").mean((2, 3))
    return (bce * valid).sum() / valid.sum().clamp_min(1)


def loss_fn(logits, y, valid):
    logits = logits.float()
    gate = valid[:, :, None, None]
    bce = F.binary_cross_entropy_with_logits(logits, y, reduction="none").mean((2, 3))
    bce = (bce * valid).sum() / valid.sum().clamp_min(1)
    p = logits.sigmoid() * gate
    t = y * gate
    inter, denom = (p * t).sum((0, 2, 3)), p.sum((0, 2, 3)) + t.sum((0, 2, 3))
    has = (valid.sum(0) > 0).float()
    dice = ((1 - (2 * inter + 1) / (denom + 1)) * has).sum() / has.sum().clamp_min(1)
    return bce + dice


def producer(samplers, sizes, device, q, stop):
    while not stop.is_set():
        parts = [s.batch(n, device) for s, n in zip(samplers, sizes)]
        q.put(tuple(torch.cat(t) for t in zip(*parts)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--smoke", action="store_true", help="tiny subset and separate output names; for testing the script")
    ap.add_argument("--variant", choices=VARIANTS, default="base",
                    help="ma_lcn: green local-contrast input, MA only, BCE + Tversky (ADR-031); focal_<L>: focal + Dice on lesion L; "
                         "enc_<L>: U-Net with an ImageNet ConvNeXt-T encoder, selected for lesion L (ADR-036)")
    args = ap.parse_args()
    device = default_device()
    variant = "" if args.variant == "base" else f"_{args.variant}"
    name = f"{TAG}{variant}_fold{args.fold}_s{SEED}" + ("_smoke" if args.smoke else "")
    path, resume = OUT / f"{name}.pt", OUT / f"{name}.resume.pt"
    oof_dir = (OOF.parent / f"{OOF.name}{variant}") / ("smoke" if args.smoke else "")
    OUT.mkdir(parents=True, exist_ok=True)
    oof_dir.mkdir(parents=True, exist_ok=True)

    ddr, idrid, train_ids, held = pools(args.fold, args.smoke)
    if not path.exists():
        torch.manual_seed(SEED + args.fold)
        rng = np.random.default_rng(SEED + args.fold)
        t0 = time.perf_counter()
        tf = None if TRANSFORM_OF[args.variant] == "base" else TRANSFORMS[TRANSFORM_OF[args.variant]]
        ddr_c = build_cache(ddr, "ddr_trainval" + variant + ("_smoke" if args.smoke else ""), tf)
        id_c = build_cache(idrid, "idrid_dev50" + variant + ("_smoke" if args.smoke else ""), tf)
        print(f"caches ready ({time.perf_counter() - t0:.0f}s): DDR {len(ddr)}, IDRiD train {len(train_ids)}, held out {len(held)}", flush=True)
        encoder = "tu-convnext_tiny.fb_in1k" if args.variant.startswith("enc_") else "resnet18"
        model = smp.Unet(encoder_name=encoder, encoder_weights="imagenet", classes=4).to(device)
        if encoder != "resnet18":
            try:
                model.encoder.model.set_grad_checkpointing(True)
            except AttributeError:
                pass
        opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
        warm = min(200, args.steps // 10)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, args.steps - warm))))
        scaler = torch.amp.GradScaler(device, enabled=device == "cuda")
        step, history = 0, []
        if resume.exists():
            st = torch.load(resume, map_location=device, weights_only=False)
            model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"]); sched.load_state_dict(st["sched"]); scaler.load_state_dict(st["scaler"])
            step, history = st["step"], st["history"]
            rng = np.random.default_rng(SEED + args.fold + step)
            print(f"resumed at step {step}", flush=True)
        samplers = [PatchSampler(*id_c, train_ids, rng), PatchSampler(*ddr_c, range(len(ddr)), np.random.default_rng(rng.integers(1 << 31)))]
        q, stop = queue.Queue(maxsize=6), threading.Event()
        threading.Thread(target=producer, args=(samplers, (3, 5), device, q, stop), daemon=True).start()
        model.train()
        losses, te = [], time.perf_counter()
        while step < args.steps:
            x, y, valid = q.get()
            with torch.autocast(device, enabled=device == "cuda"):
                logits = model(x)
            if args.variant == "ma_lcn":  # MA channel only: other lesions are not supervised
                valid = valid * torch.tensor([1.0, 0.0, 0.0, 0.0], device=valid.device)
                loss = loss_fn(logits, y, valid) + tversky_loss(logits, y, valid)
            elif args.variant.startswith("focal_"):  # focal replaces BCE on the chosen lesion; Dice kept (ADR-036)
                lesion = args.variant.split("_")[1]
                k = ["MA", "HE", "EX", "SE"].index(lesion)
                rest = valid * torch.tensor([0.0 if i == k else 1.0 for i in range(4)], device=valid.device)
                only = valid - rest
                loss = loss_fn(logits, y, rest) + focal_term(logits, y, valid, lesion) + loss_fn(logits, y, only) - bce_part(logits, y, only)
            else:
                loss = loss_fn(logits, y, valid)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite loss at step {step}")
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            losses.append(loss.item())
            step += 1
            if step % STEPS_PER_EPOCH == 0 or step == args.steps:
                history.append(dict(step=step, loss=float(np.mean(losses)), seconds=time.perf_counter() - te))
                print(f"{name} step {step}/{args.steps}: loss {history[-1]['loss']:.4f} ({history[-1]['seconds']:.0f}s)", flush=True)
                torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), scaler=scaler.state_dict(),
                                step=step, history=history), resume)
                losses, te = [], time.perf_counter()
        stop.set()
        torch.save(model.state_dict(), path)
        path.with_suffix(".json").write_text(json.dumps(dict(
            description=f"A3 U-Net/ResNet18{variant}, FOV crop {1536} px, 512 px patches, sliding window; fold {args.fold}", variant=args.variant, encoder=("tu-convnext_tiny.fb_in1k" if args.variant.startswith("enc_") else "resnet18"),
            train_data=f"DDR lesion seg train+valid ({len(ddr)}) + IDRiD seg dev images outside fold {args.fold} ({len(train_ids)})",
            eval_overlap="none with IDRiD fold %d; DDR-test never trained on" % args.fold, steps=args.steps, history=history,
            peak_vram_mib=torch.cuda.max_memory_allocated() / 2**20 if device == "cuda" else None), indent=2))
        resume.unlink(missing_ok=True)
        del model
        torch.cuda.empty_cache()

    seg = A3Segmenter(path, device, MEAN, STD)
    for r in held:
        out = oof_dir / f"{r['image_id']}.npz"
        if out.exists():
            continue
        maps, box = seg.probs(data.load_image(r["image_filepath"]))
        np.savez_compressed(out, maps=(maps * 255).round().astype(np.uint8), box=np.array(box), fold=args.fold)
    print(f"RESULT: A3 fold {args.fold} trained; {len(held)} out-of-fold maps in {oof_dir.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
