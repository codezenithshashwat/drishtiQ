"""5-fold cross-validated reproduction of the v0 segmentation recipe, producing out-of-fold (OOF) lesion maps.

Folds over the 50 IDRiD development segmentation images: folds 0-3 split the 40 dev-train images, fold 4 is the
frozen 10-image validation split, so the fold-4 models are the v0 recipe retrained on exactly v0's data.
Recipes (copied from the model-selection study):
  SegFormer-B0 @512, BCE + Dice with unavailable masks gated out, AdamW 3e-4, 6 epochs x 2 repeats, batch 1, AMP;
  MA U-Net/ResNet18 @512, 0.5 weighted BCE + 0.5 Tversky (a=.3, b=.7), 12 epochs x 2 repeats, FP32.
OOF maps are cached as uint8 (letterboxed 512x512) in results/cache/segcv/ for post-processing selection.

    .venv\\Scripts\\python src\\train\\seg_cv.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from eval import data  # noqa: E402
from inference import default_device, letterbox, to_tensor  # noqa: E402
import segmentation_models_pytorch as smp  # noqa: E402

CACHE = ROOT / "results/cache/segcv"
OUT = ROOT / "models/checkpoints/phase1/segcv"
SEED = 17
SIZE = 512


def folds():
    train, _ = data.load_split("idrid_seg_train")
    val, _ = data.load_split("idrid_seg_val")
    rng = np.random.default_rng(data.SPLIT_SEED)
    order = rng.permutation(len(train))
    assignment = {train[i]["image_id"]: k % 4 for k, i in enumerate(order)}
    assignment.update({r["image_id"]: 4 for r in val})
    return train + val, assignment


def letterbox_mask(mask, box):
    left, top, nw, nh = box
    out = np.zeros((SIZE, SIZE), np.float32)
    out[top:top + nh, left:left + nw] = np.asarray(Image.fromarray(mask.astype(np.uint8)).resize((nw, nh), Image.Resampling.NEAREST))
    return out


def prepare(rows, device):
    items = []
    for r in rows:
        im = data.load_image(r["image_filepath"])
        x512, box = letterbox(im, SIZE)
        y = np.zeros((4, SIZE, SIZE), np.float32)
        valid = np.zeros(4, np.float32)
        for i, lesion in enumerate(data.LESIONS):
            if r[f"{lesion}_mask"]:
                y[i] = letterbox_mask(data.load_mask(r[f"{lesion}_mask"]), box)
                valid[i] = 1
        spatial = np.zeros((SIZE, SIZE), np.float32)
        left, top, nw, nh = box
        spatial[top:top + nh, left:left + nw] = 1
        items.append(dict(id=r["image_id"], x=to_tensor(x512, device)[0], y=torch.tensor(y, device=device),
                          valid=torch.tensor(valid, device=device), spatial=torch.tensor(spatial, device=device), box=box))
    return items


def freeze_bn(model):
    for m in model.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()


def bce_dice(logits, y, valid, spatial):
    logits = logits.float()
    gate = valid[:, :, None, None] * spatial[:, None]
    bce = nn.functional.binary_cross_entropy_with_logits(logits, y, reduction="none")
    pixel = (bce * gate).sum() / gate.sum().clamp_min(1)
    p = logits.sigmoid() * spatial[:, None]
    t = y * spatial[:, None]
    dice = 1 - (2 * (p * t).sum((2, 3)) + 1) / (p.sum((2, 3)) + t.sum((2, 3)) + 1)
    return pixel + (dice * valid).sum() / valid.sum().clamp_min(1)


def bce_tversky(logits, y, spatial, pos_weight):
    z = logits[:, 0].float()
    bce = nn.functional.binary_cross_entropy_with_logits(z, y, reduction="none", pos_weight=torch.tensor(pos_weight, device=z.device))
    bce = (bce * spatial).sum() / spatial.sum().clamp_min(1)
    p = z.sigmoid()
    tp, fp, fn = (p * y * spatial).sum(), (p * (1 - y) * spatial).sum(), ((1 - p) * y * spatial).sum()
    return 0.5 * bce + 0.5 * (1 - (tp + 1) / (tp + 0.3 * fp + 0.7 * fn + 1))


def epochs(model, items, n_epochs, step, rng):
    for _ in range(n_epochs):
        model.train()
        freeze_bn(model)
        order = [it for it in items for _ in range(2)]
        rng.shuffle(order)
        for it in order:
            flip = rng.random() < 0.5
            step(*(t.flip(-1) if flip else t for t in (it["x"], it["y"], it["spatial"])), it["valid"])


def train_segformer(items, device):
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    model = smp.Segformer(encoder_name="mit_b0", encoder_weights="imagenet", classes=4, decoder_segmentation_channels=128).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scaler = torch.amp.GradScaler(device, enabled=device == "cuda")

    def step(x, y, spatial, valid):
        opt.zero_grad()
        with torch.autocast(device, enabled=device == "cuda"):
            logits = model(x[None])
        loss = bce_dice(logits, y[None], valid[None], spatial[None])
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 5)
        scaler.step(opt)
        scaler.update()

    epochs(model, items, 6, step, rng)
    return model.eval()


def train_ma(items, device):
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    positive = sum(float(it["y"][0].sum()) for it in items)
    pixels = sum(float(it["spatial"].sum()) for it in items)
    pos_weight = float(min(50, (pixels - positive) / positive))
    model = smp.Unet(encoder_name="resnet18", encoder_weights="imagenet", classes=1, decoder_channels=(128, 64, 32, 16, 16)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    def step(x, y, spatial, valid):
        opt.zero_grad()
        loss = bce_tversky(model(x[None]), y[None, 0], spatial[None], pos_weight)
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite MA loss")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 5)
        opt.step()

    epochs(model, items, 12, step, rng)
    return model.eval(), pos_weight


def main():
    device = default_device()
    rows, fold_of = folds()
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (CACHE / "folds.json").write_text(json.dumps(fold_of, indent=2))
    items = {it["id"]: it for it in prepare(rows, device)}
    log = {}
    for k in range(5):
        train_items = [items[i] for i, f in fold_of.items() if f != k]
        held = [items[i] for i, f in fold_of.items() if f == k]
        seg4 = train_segformer(train_items, device)
        ma, pos_weight = train_ma(train_items, device)
        for name, model in (("segformer", seg4), ("ma_unet", ma)):
            path = OUT / f"{name}_fold{k}_s{SEED}.pt"
            if not path.exists():
                torch.save(model.state_dict(), path)
        with torch.no_grad():
            for it in held:
                maps = seg4(it["x"][None]).sigmoid()[0].cpu().numpy()
                maps[0] = ma(it["x"][None]).sigmoid()[0, 0].cpu().numpy()
                np.savez_compressed(CACHE / f"{it['id']}.npz", maps=(maps * 255).round().astype(np.uint8), box=np.array(it["box"]), fold=k)
        log[k] = dict(train=len(train_items), held_out=[it["id"] for it in held], ma_pos_weight=pos_weight)
        print(f"fold {k}: trained on {len(train_items)}, wrote {len(held)} OOF maps", flush=True)
        del seg4, ma
        torch.cuda.empty_cache()
    (CACHE / "training_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
