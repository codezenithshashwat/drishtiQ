"""Inference for linear-probe graders trained by src/train/feature_head.py (seed ensemble, probabilities averaged)."""
import json
from pathlib import Path

import numpy as np
import torch

from .backbones import Backbone, fovcrop
from .pipeline import default_device, sha256


class FeatureHeadGrader:
    def __init__(self, head_paths, device=None):
        self.device = device or default_device()
        paths = [Path(p) for p in head_paths]
        cfgs = [json.loads(p.with_suffix(".json").read_text()) for p in paths]
        if len({(c["backbone"], c["preprocessing"]) for c in cfgs}) != 1:
            raise ValueError("ensemble members must share backbone and preprocessing")
        self.size = int(cfgs[0]["preprocessing"].removeprefix("fovcrop"))
        self.backbone = Backbone(cfgs[0]["backbone"], self.device)
        heads = [torch.load(p, map_location="cpu", weights_only=True) for p in paths]
        self.w = torch.stack([h["head"]["weight"] for h in heads]).float().to(self.device)
        self.b = torch.stack([h["head"]["bias"] for h in heads]).float().to(self.device)
        self.mean = torch.stack([h["feature_mean"] for h in heads]).float().to(self.device)
        self.std = torch.stack([h["feature_std"] for h in heads]).float().to(self.device)
        self.checkpoints = {p.name: sha256(p) for p in paths}

    @torch.no_grad()
    def probs(self, im):
        f = self.backbone(fovcrop(im, self.size)[None])[0]
        logits = torch.einsum("hd,hkd->hk", (f - self.mean) / self.std, self.w) + self.b
        return logits.softmax(1).mean(0).cpu().numpy()
