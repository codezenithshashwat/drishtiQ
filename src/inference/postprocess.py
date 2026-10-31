"""Lesion-map post-processing shared by the app and the evaluation harness.

Steps (each switchable via a params dict, see configs/postprocess/):
  1. field-of-view mask (eroded), removes rim artefacts;
  2. optic-disc masking for selected lesions (EX/MA false positives cluster on the bright disc);
  3. per-lesion threshold;
  4. connected-component area filter (native pixels, rescaled to the working resolution).
The optic-disc locator is a non-learned brightness heuristic; its accuracy is reported in the registry notes.
"""
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

REF_WIDTH = 4288  # IDRiD native width; component areas are specified at this scale

DEFAULT = {
    "fov_erode_frac": 0.0,
    "od_mask_lesions": [],
    "od_radius_factor": 1.0,
    "thresholds": {"MA": 0.5, "HE": 0.5, "EX": 0.5, "SE": 0.5},
    "min_area": {"MA": 0, "HE": 0, "EX": 0, "SE": 0},
    "max_area": {"MA": None, "HE": None, "EX": None, "SE": None},
}


def merged(params):
    p = {**DEFAULT, **(params or {})}
    for k in ("thresholds", "min_area", "max_area"):
        p[k] = {**DEFAULT[k], **(params or {}).get(k, {})}
    return p


def fov_mask(im, size, erode_frac=0.0):
    """Retina field of view at `size` (w, h): pixels brighter than the black surround."""
    fov = np.asarray(im.resize(size, Image.Resampling.BILINEAR).convert("L"), np.float32) > 15
    fov = ndi.binary_fill_holes(ndi.binary_opening(fov, iterations=2))
    if erode_frac > 0:
        fov = ndi.binary_erosion(fov, iterations=max(1, round(erode_frac * size[0])))
    return fov


# Disc radius as a fraction of field-of-view width: median over the 50 IDRiD dev segmentation OD masks
# (p10-p90 0.071-0.086). On those images the locator puts the centre within one disc radius in 49/50.
OD_RADIUS_FRAC = 0.077


def locate_optic_disc(im):
    """Returns (cx, cy, r) in the image's own pixel coordinates."""
    w = 512
    scale = im.width / w
    small = np.asarray(im.resize((w, round(im.height / scale)), Image.Resampling.BILINEAR), np.float32)
    fov = small.max(2) > 15
    inner = ndi.binary_erosion(fov, iterations=12)
    # The disc is the largest bright, roughly disc-sized blob; heavy blurring suppresses small bright exudates.
    bright = 0.5 * small[..., 0] + 0.5 * small[..., 1]
    blurred = ndi.gaussian_filter(np.where(fov, bright, 0), sigma=12) / np.maximum(ndi.gaussian_filter(fov.astype(np.float32), sigma=12), 1e-3)
    blurred[~inner] = -1
    cy, cx = np.unravel_index(int(blurred.argmax()), blurred.shape)
    cols = np.flatnonzero(fov.any(0))
    fov_width = (cols.max() - cols.min() + 1) if len(cols) else w
    return (cx + 0.5) * scale, (cy + 0.5) * scale, OD_RADIUS_FRAC * fov_width * scale


def disc_mask(shape_hw, od, image_size, factor):
    """Boolean disc mask at an output resolution `shape_hw` for a disc located in image coordinates."""
    h, w = shape_hw
    sx, sy = w / image_size[0], h / image_size[1]
    cx, cy, r = od[0] * sx, od[1] * sy, od[2] * factor * sx
    yy, xx = np.ogrid[:h, :w]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r


def masked_probs(prob, lesion, im, params, od=None, fov=None):
    """Zero probabilities outside the FOV and, for selected lesions, inside the optic disc."""
    p = merged(params)
    shape = prob.shape
    if fov is None:
        fov = fov_mask(im, (shape[1], shape[0]), p["fov_erode_frac"])
    out = np.where(fov, prob, 0)
    if lesion in p["od_mask_lesions"]:
        od = od or locate_optic_disc(im)
        out = np.where(disc_mask(shape, od, im.size, p["od_radius_factor"]), 0, out)
    return out


def binarize(prob, lesion, params, image_width):
    """Threshold and filter components by area (areas given at REF_WIDTH, rescaled to this map's resolution)."""
    p = merged(params)
    mask = prob >= p["thresholds"][lesion]
    lo, hi = p["min_area"][lesion], p["max_area"][lesion]
    if not lo and hi is None:
        return mask
    s2 = (image_width / REF_WIDTH) ** 2
    labels, n = ndi.label(mask, np.ones((3, 3)))
    if n == 0:
        return mask
    areas = np.bincount(labels.ravel())[1:] / s2
    keep = areas >= lo
    if hi is not None:
        keep &= areas <= hi
    return np.concatenate([[False], keep])[labels]
