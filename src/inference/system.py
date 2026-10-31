"""The grading system (ADR-033): base grader -> thresholds (S1) -> specialists (S2 stage 0/1, S3 stage 3/4) -> TTA.

Every part is optional and lives under configs/app/app.json "system"; each is adopted only by its pre-registered
rule. A3 lesion fusion (ADR-021) is applied in the pipeline after segmentation and is not part of this module.

    "system": {"thresholds": "configs/grading/s1_thresholds.json",
               "specialists": {"stage01": "models/checkpoints/phase2/specialists/<x>.pt", "stage34": "..."},
               "tta": true}
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from .finetuned import build, regression_to_grade
from .preprocess import PREPROCESSORS

ROOT = Path(__file__).resolve().parents[2]
TTA_ANGLES = (8, -8)  # ADR-030: original + horizontal flip + rotations of +-8 degrees


def system_name(app):
    """Registry model name of the app's grading system (the grader spec alone when no system part is active)."""
    sysc = app.get("system") or {}
    if not any(sysc.values()):
        return app["grader"]
    key = json.dumps(dict(grader=app["grader"], system=sysc), sort_keys=True)
    return f"system:{hashlib.sha256(key.encode()).hexdigest()[:10]}"


def tta_images(im):
    flip = ImageOps.mirror(im)
    return [im, flip] + [im.rotate(a, resample=Image.Resampling.BILINEAR) for a in TTA_ANGLES]


class Specialist:
    """Binary ConvNeXt specialist (ADR-028); its json sidecar holds arch, size, preprocessing, threshold, low/high stage."""

    def __init__(self, path, device):
        path = ROOT / path
        self.cfg = json.loads(path.with_suffix(".json").read_text())
        self.model = build(self.cfg["arch"], "bin")
        self.model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
        self.model = self.model.to(device).eval()
        self.device = device

    @torch.no_grad()
    def prob(self, im):
        from .pipeline import MEAN, STD
        x = (PREPROCESSORS[self.cfg["preprocessing"]](im, self.cfg["size"]).astype(np.float32) / 255 - MEAN) / STD
        x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        with torch.autocast(self.device, enabled=self.device == "cuda"):
            return float(torch.sigmoid(self.model(x).float()[0, 0]))

    def decide(self, im):
        return self.cfg["high_stage"] if self.prob(im) >= self.cfg["threshold"] else self.cfg["low_stage"]


class GradingSystem:
    def __init__(self, app, grader, device):
        self.app, self.grader, self.device = app, grader, device
        sysc = app.get("system") or {}
        if sysc.get("thresholds"):
            grader.thresholds = np.asarray(json.loads((ROOT / sysc["thresholds"]).read_text())["thresholds"], dtype=float)
        self.tta = bool(sysc.get("tta"))
        self.specialists = {k: Specialist(v, device) for k, v in (sysc.get("specialists") or {}).items()}
        self.name = system_name(app)

    @property
    def thresholds(self):
        return self.grader.thresholds

    def score(self, im):
        if not self.tta:
            return self.grader.predict(im)[1]
        return float(np.mean([self.grader.predict(x)[1] for x in tta_images(im)]))

    def stage(self, score, im):
        s = regression_to_grade(score, self.thresholds)
        if s <= 1 and "stage01" in self.specialists:
            s = self.specialists["stage01"].decide(im)
        elif s >= 3 and "stage34" in self.specialists:
            s = self.specialists["stage34"].decide(im)
        return s

    @property
    def changes_stage(self):
        """True when the stage no longer follows the calibrated score alone (specialists), so ADR-019 does not apply."""
        return bool(self.specialists)
