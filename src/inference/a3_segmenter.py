"""A3 lesion segmenter: 4-channel U-Net (ResNet18) on the FOV crop at FOV_PX, Gaussian sliding-window inference.

probs(im) returns maps in the same convention as V0Segmenter (a map plus a box for crop_back), so the evaluation
harness, post-processing selection and the app use it unchanged. The map covers the whole image at OUT_W px wide;
the box is the full map. Several checkpoints (fold ensemble) are averaged; tta adds a horizontal flip (ADR-031).
A checkpoint's sidecar json may name an input "variant": "ma_lcn" = green-channel local contrast normalisation
(ADR-031a), applied identically in training (seg_a3.py) and here.

Specs: a3:<ckpt>  ·  a3tta:<ckpt> (flip TTA)  ·  a3ens:<glob> (mean of all matching checkpoints + flip TTA)
"""
import glob
import hashlib
import json
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image
from scipy import ndimage as ndi

from .preprocess import crop_to_fov, square_to_image

FOV_PX, PATCH, OUT_W = 1536, 512, 2048
ROOT = Path(__file__).resolve().parents[2]


def build(encoder="resnet18"):
    """U-Net with the given encoder (A3: resnet18; ADR-036 encoder upgrade: tu-convnext_tiny.fb_in1k)."""
    return smp.Unet(encoder_name=encoder, encoder_weights=None, classes=4)


def lcn_green(sq):
    """(H, W, 3) uint8 -> green-channel local contrast normalisation (sigma 8 px), clipped to +-3 SD, as 3 channels."""
    g = sq[..., 1].astype(np.float32)
    mu = ndi.gaussian_filter(g, 8)
    sd = np.sqrt(ndi.gaussian_filter((g - mu) ** 2, 8)) + 1e-3
    z = np.clip((g - mu) / sd, -3, 3)
    out = ((z + 3) / 6 * 255).astype(np.uint8)
    return np.repeat(out[..., None], 3, 2)


TRANSFORMS = {"base": lambda sq: sq, "ma_lcn": lcn_green}
# Training variants -> input transform. focal_<L> / enc_<L> (ADR-036) use the plain input.
VARIANTS = ["base", "ma_lcn"] + [f"{k}_{l}" for k in ("focal", "enc") for l in ("MA", "HE", "EX", "SE")]
TRANSFORM_OF = {v: ("ma_lcn" if v == "ma_lcn" else "base") for v in VARIANTS}


def gaussian_window(size=PATCH, sigma_frac=0.25):
    g = np.exp(-((np.arange(size) - (size - 1) / 2) ** 2) / (2 * (sigma_frac * size) ** 2))
    return np.outer(g, g).astype(np.float32)


@torch.no_grad()
def sliding_window(model, img_sq, device, mean, std, stride=384, batch=4):
    """img_sq: (FOV_PX, FOV_PX, 3) uint8 -> (4, FOV_PX, FOV_PX) probabilities, Gaussian-blended."""
    w = torch.from_numpy(gaussian_window()).to(device)
    out = torch.zeros((4, FOV_PX, FOV_PX), device=device)
    norm = torch.zeros((FOV_PX, FOV_PX), device=device)
    starts = list(range(0, FOV_PX - PATCH + 1, stride))
    if starts[-1] != FOV_PX - PATCH:
        starts.append(FOV_PX - PATCH)
    coords = [(t, l) for t in starts for l in starts]
    x = torch.from_numpy(np.array(img_sq)).to(device).permute(2, 0, 1).float() / 255
    x = (x - torch.tensor(mean, device=device).view(3, 1, 1)) / torch.tensor(std, device=device).view(3, 1, 1)
    for i in range(0, len(coords), batch):
        cs = coords[i:i + batch]
        xb = torch.stack([x[:, t:t + PATCH, l:l + PATCH] for t, l in cs])
        with torch.autocast(device, enabled=device == "cuda"):
            pb = model(xb).float().sigmoid()
        for p, (t, l) in zip(pb, cs):
            out[:, t:t + PATCH, l:l + PATCH] += p * w
            norm[t:t + PATCH, l:l + PATCH] += w
    return (out / norm.clamp_min(1e-6)).cpu().numpy()


def paths_for(spec):
    kind, _, rest = spec.partition(":")
    paths = sorted(glob.glob(str(ROOT / rest))) if kind == "a3ens" else [str(ROOT / rest)]
    if not paths:
        raise FileNotFoundError(f"no checkpoint matches {spec}")
    return paths, kind in ("a3ens", "a3tta")


class A3Segmenter:
    def __init__(self, ckpt_paths, device, mean, std, tta=False):
        paths = [ckpt_paths] if isinstance(ckpt_paths, (str, Path)) else list(ckpt_paths)
        self.device, self.mean, self.std, self.tta = device, mean, std, tta
        self.models, self.checkpoints, variants = [], {}, set()
        for p in map(Path, paths):
            side = p.with_suffix(".json")
            info = json.loads(side.read_text()) if side.exists() else {}
            m = build(info.get("encoder", "resnet18"))
            m.load_state_dict(torch.load(p, map_location="cpu", weights_only=True))
            self.models.append(m.to(device).eval())
            self.checkpoints[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
            variants.add(TRANSFORM_OF.get(info.get("variant", "base"), "base"))
        if len(variants) != 1:
            raise ValueError(f"ensemble members use different input variants: {variants}")
        self.variant = variants.pop()

    @classmethod
    def from_spec(cls, spec, device, mean, std):
        paths, tta = paths_for(spec)
        return cls(paths, device, mean, std, tta=tta)

    def probs(self, im):
        """(4, H, OUT_W) probabilities over the whole image (MA, HE, EX, SE) and the crop_back box."""
        sq = TRANSFORMS[self.variant](np.asarray(crop_to_fov(im).resize((FOV_PX, FOV_PX), Image.Resampling.BILINEAR)))
        acc = []
        for m in self.models:
            acc.append(sliding_window(m, sq, self.device, self.mean, self.std))
            if self.tta:
                acc.append(sliding_window(m, sq[:, ::-1], self.device, self.mean, self.std)[:, :, ::-1])
        maps = np.mean(acc, 0)
        size = (OUT_W, round(OUT_W * im.height / im.width))
        full = np.stack([square_to_image(m, im, size) for m in maps])
        return full, (0, 0, size[0], size[1])
