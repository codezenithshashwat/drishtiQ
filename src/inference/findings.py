"""Evidence engine: one structured findings record per image, the single source of truth for the UI, reports and
explanations. All coordinates are in the display image frame (long side 1024 px).

Quadrants are anchored on the disc-fovea axis: origin at the fovea, nasal = towards the disc, superior = the image-up
side of that axis (assumes the photograph is not flipped vertically). Distances are in disc diameters (DD), using the
disc radius from the optic-disc locator (0.077 x FOV width).
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
QUADRANTS = ["superior-temporal", "superior-nasal", "inferior-temporal", "inferior-nasal"]
# Exudate regions smaller than this many display pixels are ignored for the macular-edema rule. Fitted on IDRiD
# dev-train by macro-F1 for the app's segmenter (src/eval/fit_dme.py); the file is named by configs/app/app.json
# "dme_rule" (v1, the v0 segmenter: 40 px; IDRiD-val high-risk sensitivity 0.86, PPV 0.81).
DME_RULE = json.loads((ROOT / "configs/app/app.json").read_text()).get("dme_rule", "configs/landmarks/dme_rule_v1.json")
DME_MIN_EX_AREA = json.loads((ROOT / DME_RULE).read_text())["min_exudate_area_px"]


def regions(mask, max_regions=200):
    labels, n = ndi.label(mask, np.ones((3, 3)))
    if n == 0:
        return []
    idx = np.arange(1, n + 1)
    area = ndi.sum(mask, labels, idx)
    cy, cx = np.array(ndi.center_of_mass(mask, labels, idx)).T
    order = np.argsort(-area)[:max_regions]
    return [dict(x=float(cx[k]), y=float(cy[k]), area_px=int(area[k])) for k in order]


def axis(od, fovea, fov_centre):
    """Origin and unit vectors (nasal u, superior w) in display coordinates."""
    origin = np.array(fovea if fovea is not None else fov_centre, float)
    u = np.array(od[:2], float) - origin
    u = u / (np.linalg.norm(u) or 1.0)
    w = np.array([u[1], -u[0]])
    if w[1] > 0:  # make w point to image-up
        w = -w
    return origin, u, w


def quadrant(x, y, origin, u, w):
    d = np.array([x, y]) - origin
    nasal, superior = float(d @ u) > 0, float(d @ w) > 0
    return f"{'superior' if superior else 'inferior'}-{'nasal' if nasal else 'temporal'}"


def build(grading, lesion_masks, lesion_names, quality, od_display, fovea_display, fovea_uncertain, fov_centre, versions, flags):
    """lesion_masks: {key: bool mask (display frame)}; od_display: (x, y, radius) in display px.
    An uncertain fovea is still used for the axis and distances; the record and the explanations say it is uncertain."""
    od_display = tuple(float(v) for v in od_display)
    fovea_display = tuple(float(v) for v in fovea_display)
    fov_centre = tuple(float(v) for v in fov_centre)
    dd = 2 * od_display[2]
    origin, u, w = axis(od_display, fovea_display, fov_centre)
    lesions = {}
    for key, mask in lesion_masks.items():
        regs = regions(mask)
        for k, r in enumerate(regs):
            r["id"] = f"{key}-{k + 1}"
            r["quadrant"] = quadrant(r["x"], r["y"], origin, u, w)
            r["distance_to_fovea_dd"] = round(float(np.hypot(r["x"] - fovea_display[0], r["y"] - fovea_display[1]) / dd), 2)
        lesions[key] = dict(name=lesion_names[key], count=len(regs), area_px=int(mask.sum()),
                            per_quadrant={q: int(sum(r["quadrant"] == q for r in regs)) for q in QUADRANTS}, regions=regs)
    he_quadrants = [q for q in QUADRANTS if lesions["HE"]["per_quadrant"][q] > 0]
    ex = [r for r in lesions["EX"]["regions"] if r["area_px"] >= DME_MIN_EX_AREA]
    nearest = min((r["distance_to_fovea_dd"] for r in ex), default=None)
    if not ex:
        dme = dict(level="low", reason="no hard exudates segmented")
    elif nearest <= 1.0:
        dme = dict(level="high", reason="hard exudate within 1 disc diameter of the fovea")
    else:
        dme = dict(level="possible", reason="hard exudates present, none within 1 disc diameter of the fovea")
    dme.update(nearest_exudate_dd=nearest, exudates_within_1dd=int(sum(r["distance_to_fovea_dd"] <= 1.0 for r in ex)),
               landmarks_uncertain=bool(fovea_uncertain), rule="IDRiD-style: EX within 1 DD of fovea = high; EX elsewhere = possible; none = low")
    return dict(
        versions=versions, quality=quality, grading=grading,
        landmarks=dict(optic_disc=dict(x=round(od_display[0], 1), y=round(od_display[1], 1), radius_px=round(od_display[2], 1)),
                       fovea=dict(x=round(fovea_display[0], 1), y=round(fovea_display[1], 1), uncertain=bool(fovea_uncertain)),
                       disc_diameter_px=round(dd, 1),
                       axis=dict(origin=[round(v, 1) for v in origin], nasal=[round(v, 4) for v in u], superior=[round(v, 4) for v in w])),
        lesions=lesions,
        haemorrhage_quadrants=dict(count=len(he_quadrants), quadrants=he_quadrants,
                                   max_per_quadrant=max(lesions["HE"]["per_quadrant"].values())),
        macular_edema_risk=dme, flags=flags)
