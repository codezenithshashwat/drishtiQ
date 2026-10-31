"""Fundus preprocessing for fine-tuned graders: circular field-of-view crop + Ben Graham local-contrast normalisation.

Ben Graham (Kaggle DR 2015): img' = 4*img - 4*GaussianBlur(img, sigma) + 128, which removes illumination gradients and
emphasises local structure (vessels, lesions); a slightly shrunk circular mask removes the bright ring artefact it
creates at the field-of-view edge.
"""
import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as ndi


def fov_box(im):
    """Bounding box (left, top, right, bottom) of the retinal field of view in image pixels."""
    w = 512
    small = np.asarray(im.resize((w, round(w * im.height / im.width))).convert("L")) > 15
    rows, cols = np.flatnonzero(small.any(1)), np.flatnonzero(small.any(0))
    if len(rows) < 10 or len(cols) < 10:
        return (0, 0, im.width, im.height)
    s = im.width / w
    # Not clamped to the image: identical to the box used to build the training caches (PIL pads outside with black).
    return (int(cols.min() * s), int(rows.min() * s), int(np.ceil((cols.max() + 1) * s)), int(np.ceil((rows.max() + 1) * s)))


def crop_to_fov(im):
    """Crop to the bounding box of the retinal field of view, padded to a centred square."""
    im = im.crop(fov_box(im))
    side = max(im.size)
    return ImageOps.pad(im, (side, side), color=(0, 0, 0))


def square_to_image(map_sq, im, out_size):
    """Map a (S, S) map defined on crop_to_fov(im) back onto the full image, resized to out_size (w, h)."""
    left, top, right, bottom = fov_box(im)
    w, h = right - left, bottom - top
    side = max(w, h)
    # ImageOps.pad centres the crop inside the square.
    ox, oy = (side - w) // 2, (side - h) // 2
    full = np.asarray(Image.fromarray(map_sq.astype(np.float32), mode="F").resize((side, side), Image.Resampling.BILINEAR))
    canvas = np.zeros((max(im.height, bottom), max(im.width, right)), np.float32)
    canvas[top:top + h, left:left + w] = full[oy:oy + h, ox:ox + w]
    canvas = canvas[:im.height, :im.width]
    return np.asarray(Image.fromarray(canvas, mode="F").resize(out_size, Image.Resampling.BILINEAR))


def ben_graham(im, size):
    """Square uint8 RGB array (size x size) after FOV crop, resize and Ben Graham normalisation."""
    x = np.asarray(crop_to_fov(im).resize((size, size), Image.Resampling.BILINEAR), np.float32)
    blur = np.stack([ndi.gaussian_filter(x[..., c], sigma=size / 30) for c in range(3)], -1)
    y = np.clip(4 * x - 4 * blur + 128, 0, 255)
    yy, xx = np.ogrid[:size, :size]
    circle = (xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2 <= (0.95 * size / 2) ** 2
    y[~circle] = 128
    return y.astype(np.uint8)


def plain(im, size):
    """FOV crop + resize only (ablation control for Ben Graham)."""
    return np.asarray(crop_to_fov(im).resize((size, size), Image.Resampling.BILINEAR), np.uint8)


PREPROCESSORS = {"ben_graham": ben_graham, "plain": plain}
