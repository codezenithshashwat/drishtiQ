"""Anatomical landmarks: optic disc (brightness heuristic, in postprocess.py) and fovea (anatomical prior + dark-spot
search), with a confidence flag. Parameters are fitted on IDRiD dev-train localisation labels (src/eval/fit_fovea.py,
configs/landmarks/fovea_v1.json); evaluated on IDRiD-val.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from .postprocess import OD_RADIUS_FRAC, locate_optic_disc

CONFIG = Path(__file__).resolve().parents[2] / "configs/landmarks/fovea_v1.json"
WORK = 512  # working width


def fov_geometry(im):
    """Downscaled float image, FOV mask, scale factor and FOV centre/width in the working frame."""
    scale = im.width / WORK
    small = np.asarray(im.convert("RGB").resize((WORK, round(im.height / scale)), Image.Resampling.BILINEAR), np.float32)
    fov = small.max(2) > 15
    cols, rows = np.flatnonzero(fov.any(0)), np.flatnonzero(fov.any(1))
    centre = ((cols.min() + cols.max()) / 2, (rows.min() + rows.max()) / 2) if len(cols) else (WORK / 2, small.shape[0] / 2)
    width = (cols.max() - cols.min() + 1) if len(cols) else WORK
    return small, fov, scale, centre, width


def fovea_candidates(im, od):
    """Precomputes what the search needs (shared by fitting and inference)."""
    small, fov, scale, centre, width = fov_geometry(im)
    dd = 2 * OD_RADIUS_FRAC * width  # disc diameter, working frame
    green = np.where(fov, small[..., 1], np.nan)
    inner = ndi.binary_erosion(fov, iterations=10)
    filled = np.where(np.isnan(green), np.nanmean(green), green)
    dark = ndi.gaussian_filter(filled, sigma=0.3 * dd)
    surround = ndi.gaussian_filter(filled, sigma=1.2 * dd)
    return dict(dark=dark, surround=surround, inner=inner, scale=scale, centre=centre, dd=dd,
                od=(od[0] / scale, od[1] / scale))


def locate_fovea(cand, params):
    """Returns (x, y, confidence, uncertain) in original image pixels."""
    od, dd = cand["od"], cand["dd"]
    direction = 1.0 if cand["centre"][0] >= od[0] else -1.0  # fovea lies on the image-centre side of the disc
    px, py = od[0] + direction * params["distance_dd"] * dd, od[1] + params["vertical_dd"] * dd
    h, w = cand["dark"].shape
    yy, xx = np.ogrid[:h, :w]
    window = ((xx - px) ** 2 + (yy - py) ** 2 <= (params["search_dd"] * dd) ** 2) & cand["inner"]
    if not window.any():
        return px * cand["scale"], py * cand["scale"], 0.0, True
    score = np.where(window, cand["dark"], np.inf)
    fy, fx = np.unravel_index(int(np.argmin(score)), score.shape)
    # Confidence: how much darker the spot is than its wider surround (macula is a distinct dark region).
    contrast = float(cand["surround"][fy, fx] - cand["dark"][fy, fx])
    return fx * cand["scale"], fy * cand["scale"], contrast, contrast < params["min_contrast"]


_PARAMS = None


def fovea(im, od=None):
    global _PARAMS
    if _PARAMS is None:
        _PARAMS = json.loads(CONFIG.read_text())["params"]
    od = od or locate_optic_disc(im)
    x, y, conf, uncertain = locate_fovea(fovea_candidates(im, od), _PARAMS)
    return dict(x=x, y=y, contrast=conf, uncertain=uncertain)
