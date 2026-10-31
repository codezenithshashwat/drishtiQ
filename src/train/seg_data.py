"""A3 segmentation data: a common physical scale, realistic-frequency patch sampling, sliding-window inference.

Scale: every image is cropped to its field of view (preprocess.crop_to_fov), padded square and resized so the FOV is
FOV_PX wide (IDRiD 4288 px and DDR 1700-3900 px images end up comparable). Masks are downscaled by area averaging and
thresholded at 1/4 coverage, which keeps tiny microaneurysms that nearest-neighbour resizing would drop.
Supervision: IDRiD masks may be missing (= unannotated, gated out of the loss); DDR annotated all four lesions, so an
empty DDR mask is a negative.
Sampling: patch centres are drawn uniformly from FOV pixels, so lesions appear at their natural frequency (the v0
recipe's 50% lesion-centred sampling inflated the lesion prior and produced false positives).
Inference: overlapping windows blended with a Gaussian weight; maps return to the original image via
preprocess.square_to_image, i.e. the same crop geometry as training.
"""
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from inference.pipeline import MEAN, STD  # noqa: E402
from inference.preprocess import crop_to_fov, fov_box  # noqa: E402

LESIONS = ["MA", "HE", "EX", "SE"]
FOV_PX = 1536
PATCH = 512
CACHE = ROOT / "results/cache/seg_a3"


def _square_mask(path, im_size, box):
    """Binary mask -> same FOV crop/pad as the image -> FOV_PX x FOV_PX uint8 (0/1)."""
    with Image.open(ROOT / path) as m:
        a = np.asarray(m)
    a = a[..., :3].max(-1) if a.ndim == 3 else a  # alpha ignored (one IDRiD EX mask is RGBA)
    m = Image.fromarray(((a > 0) * 255).astype(np.uint8))
    if m.size != im_size:
        m = m.resize(im_size, Image.Resampling.NEAREST)
    m = m.crop(box)
    side = max(m.size)
    m = ImageOps.pad(m, (side, side), color=0)
    return (np.asarray(m.resize((FOV_PX, FOV_PX), Image.Resampling.BOX)) >= 64).astype(np.uint8)


def build_cache(rows, key, transform=None):
    """rows: dicts with image_filepath and <LESION>_mask columns ('' = unannotated). Returns memmaps (img, mask, valid).
    transform: optional (H, W, 3) uint8 -> (H, W, 3) uint8 input variant, applied before caching (use a distinct key)."""
    digest = hashlib.sha256("|".join(r["image_filepath"] for r in rows).encode()).hexdigest()[:10]
    base = CACHE / f"{key}_{FOV_PX}_{digest}"
    paths = [base.with_suffix(s) for s in (".img.npy", ".mask.npy", ".valid.npy")]
    if all(p.exists() for p in paths):
        return tuple(np.load(p, mmap_mode="r") for p in paths)
    CACHE.mkdir(parents=True, exist_ok=True)
    img = np.lib.format.open_memmap(base.with_suffix(".img.partial.npy"), "w+", np.uint8, (len(rows), FOV_PX, FOV_PX, 3))
    mask = np.lib.format.open_memmap(base.with_suffix(".mask.partial.npy"), "w+", np.uint8, (len(rows), 4, FOV_PX, FOV_PX))
    valid = np.zeros((len(rows), 4), np.uint8)

    def work(i):
        r = rows[i]
        with Image.open(ROOT / r["image_filepath"]) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            box = fov_box(im)
            sq = np.asarray(crop_to_fov(im).resize((FOV_PX, FOV_PX), Image.Resampling.BILINEAR))
            img[i] = transform(sq) if transform else sq
            for k, lesion in enumerate(LESIONS):
                if r.get(f"{lesion}_mask"):
                    mask[i, k] = _square_mask(r[f"{lesion}_mask"], im.size, box)
                    valid[i, k] = 1
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(work, range(len(rows))))
    img.flush()
    mask.flush()
    del img, mask
    base.with_suffix(".img.partial.npy").replace(paths[0])
    base.with_suffix(".mask.partial.npy").replace(paths[1])
    np.save(paths[2], valid)
    return tuple(np.load(p, mmap_mode="r") for p in paths)


def fov_disc(size=FOV_PX):
    yy, xx = np.ogrid[:size, :size]
    return (xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2 <= (0.97 * size / 2) ** 2


class PatchSampler:
    """Uniform patch centres within the FOV disc (natural lesion frequency); random flips/rot90 on the fly."""

    def __init__(self, img, mask, valid, indices, rng):
        self.img, self.mask, self.valid, self.indices, self.rng = img, mask, valid, np.asarray(indices), rng
        ys, xs = np.nonzero(fov_disc())
        self.centres = np.stack([ys, xs], 1)

    def batch(self, n, device):
        ids = self.rng.choice(self.indices, n)
        cs = self.centres[self.rng.integers(0, len(self.centres), n)]
        x = np.empty((n, PATCH, PATCH, 3), np.uint8)
        y = np.empty((n, 4, PATCH, PATCH), np.uint8)
        for j, (i, (cy, cx)) in enumerate(zip(ids, cs)):
            t = int(np.clip(cy - PATCH // 2, 0, FOV_PX - PATCH))
            l = int(np.clip(cx - PATCH // 2, 0, FOV_PX - PATCH))
            a, b = self.img[i, t:t + PATCH, l:l + PATCH], self.mask[i, :, t:t + PATCH, l:l + PATCH]
            k = int(self.rng.integers(4))
            if self.rng.random() < 0.5:
                a, b = a[:, ::-1], b[:, :, ::-1]
            x[j], y[j] = np.rot90(a, k, (0, 1)), np.rot90(b, k, (1, 2))
        xt = torch.from_numpy(x).to(device).permute(0, 3, 1, 2).float() / 255
        xt = (xt - torch.tensor(MEAN, device=device).view(1, 3, 1, 1)) / torch.tensor(STD, device=device).view(1, 3, 1, 1)
        return xt, torch.from_numpy(y).to(device).float(), torch.from_numpy(self.valid[ids].astype(np.float32)).to(device)


def gaussian_window(size=PATCH, sigma_frac=0.25):
    g = np.exp(-((np.arange(size) - (size - 1) / 2) ** 2) / (2 * (sigma_frac * size) ** 2))
    return np.outer(g, g).astype(np.float32)


@torch.no_grad()
def sliding_window(model, img_sq, device, stride=384, channels=4, batch=4):
    """img_sq: (FOV_PX, FOV_PX, 3) uint8 -> (channels, FOV_PX, FOV_PX) probabilities, Gaussian-blended."""
    w = torch.from_numpy(gaussian_window()).to(device)
    out = torch.zeros((channels, FOV_PX, FOV_PX), device=device)
    norm = torch.zeros((FOV_PX, FOV_PX), device=device)
    starts = list(range(0, FOV_PX - PATCH + 1, stride))
    if starts[-1] != FOV_PX - PATCH:
        starts.append(FOV_PX - PATCH)
    coords = [(t, l) for t in starts for l in starts]
    x_all = torch.from_numpy(np.ascontiguousarray(img_sq)).to(device).permute(2, 0, 1).float() / 255
    x_all = (x_all - torch.tensor(MEAN, device=device).view(3, 1, 1)) / torch.tensor(STD, device=device).view(3, 1, 1)
    for i in range(0, len(coords), batch):
        cs = coords[i:i + batch]
        xb = torch.stack([x_all[:, t:t + PATCH, l:l + PATCH] for t, l in cs])
        with torch.autocast(device, enabled=device == "cuda"):
            pb = model(xb).float().sigmoid()
        for p, (t, l) in zip(pb, cs):
            out[:, t:t + PATCH, l:l + PATCH] += p * w
            norm[t:t + PATCH, l:l + PATCH] += w
    return (out / norm.clamp_min(1e-6)).cpu().numpy()
