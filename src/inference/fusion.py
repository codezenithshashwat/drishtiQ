"""A4 lesion-to-grade fusion (ADR-021): a multinomial logistic regression on the grader score and lesion summaries.

Features are computed at display size from the app's post-processed lesion masks, so the fitting script and the app
compute them identically. Used by the app only when configs/app/app.json names a fusion file (adopted by rule).
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

FEATURES = ["grader_score", "log1p_MA_count", "log1p_HE_count", "HE_quadrants", "log1p_EX_area", "log1p_SE_area"]


def regions(mask):
    return int(ndi.label(mask, np.ones((3, 3)))[1])


def features(score, masks, fov):
    """masks: {lesion: bool array at display size}; fov: bool FOV mask at the same size."""
    ys, xs = np.nonzero(fov)
    cy, cx = (ys.mean(), xs.mean()) if len(ys) else (fov.shape[0] / 2, fov.shape[1] / 2)
    hy, hx = np.nonzero(masks["HE"])
    quads = len({(int(y < cy), int(x < cx)) for y, x in zip(hy, hx)}) if len(hy) else 0
    return np.array([score, np.log1p(regions(masks["MA"])), np.log1p(regions(masks["HE"])), quads,
                     np.log1p(masks["EX"].sum()), np.log1p(masks["SE"].sum())], np.float64)


class Fusion:
    def __init__(self, path):
        cfg = json.loads(Path(path).read_text())
        self.path, self.mean, self.std = Path(path), np.array(cfg["mean"]), np.array(cfg["std"])
        self.coef, self.intercept = np.array(cfg["coef"]), np.array(cfg["intercept"])

    def probs(self, x):
        z = self.coef @ ((np.asarray(x) - self.mean) / self.std) + self.intercept
        e = np.exp(z - z.max())
        return e / e.sum()
