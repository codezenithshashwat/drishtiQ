"""Inference for fine-tuned timm graders (CE or ordinal-regression heads), optionally a seed ensemble."""
import json
from pathlib import Path

import numpy as np
import timm
import torch

from .pipeline import MEAN, STD, default_device, sha256
from .preprocess import PREPROCESSORS, square_to_image


def build(arch, head, pretrained=False):
    """ce: 5 logits; corn: 4 conditional ordinal logits (ADR-029); regbin: score + referable logit (ADR-041); reg / bin: 1 output."""
    return timm.create_model(arch, pretrained=pretrained, num_classes={"ce": 5, "corn": 4, "regbin": 2}.get(head, 1))


def corn_score(logits):
    """Expected rank from CORN logits: sum_k P(y > k) with P(y > k) = prod_{j <= k} sigmoid(logit_j); in [0, 4]."""
    return torch.cumprod(torch.sigmoid(logits), -1).sum(-1)


def regression_to_grade(score, thresholds):
    return int(np.searchsorted(np.asarray(thresholds), score, side="right"))


class FinetunedGrader:
    def __init__(self, ckpt_paths, device=None):
        self.device = device or default_device()
        self.models, self.configs, self.checkpoints = [], [], {}
        for path in map(Path, ckpt_paths):
            cfg = json.loads(path.with_suffix(".json").read_text())
            model = build(cfg["arch"], cfg["head"])
            model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
            model.requires_grad_(False)
            self.models.append(model.to(self.device).eval())
            self.configs.append(cfg)
            self.checkpoints[path.name] = sha256(path)
        keys = {(c["arch"], c["head"], c["size"], c["preprocessing"]) for c in self.configs}
        if len(keys) != 1:
            raise ValueError(f"ensemble members must share arch/head/size/preprocessing: {keys}")
        self.arch, self.head, self.size, self.prep = keys.pop()
        self.thresholds = np.mean([c["thresholds"] for c in self.configs], 0)

    def tensor(self, im):
        x = (PREPROCESSORS[self.prep](im, self.size).astype(np.float32) / 255 - MEAN) / STD  # MEAN/STD are channel-last
        x = x.transpose(2, 0, 1)
        return torch.from_numpy(x).unsqueeze(0).to(self.device)

    def _summarise(self, outs):
        """outs: list of per-model output tensors (1-D)."""
        if self.head == "ce":
            per = torch.stack([o.softmax(0) for o in outs])
            probs = per.mean(0)
            votes = per.argmax(1)
            return probs, int(probs.argmax()), votes, None
        scores = torch.stack([corn_score(o) if self.head == "corn" else o[0] for o in outs])
        score = float(scores.mean())
        pred = regression_to_grade(score, self.thresholds)
        probs = torch.zeros(5)
        probs[pred] = 1.0  # regression has no calibrated distribution
        votes = torch.tensor([regression_to_grade(float(s), self.thresholds) for s in scores])
        return probs, pred, votes, score

    @torch.no_grad()
    def predict(self, im):
        """Returns (probabilities over 5 grades, continuous score or None)."""
        x = self.tensor(im)
        with torch.autocast(self.device, enabled=self.device == "cuda"):
            outs = [m(x).float()[0] for m in self.models]
        probs, _, _, score = self._summarise(outs)
        return probs.cpu().numpy(), score

    def probs(self, im):
        return self.predict(im)[0]

    def grade_with_cam(self, im, display_size):
        """Grad-CAM on the last ConvNeXt stage, averaged over ensemble members, mapped onto the display image."""
        x = self.tensor(im).requires_grad_(True)
        outs, cams = [], []
        for m in self.models:
            acts = {}
            hook = m.stages[-1].register_forward_hook(lambda mod, i, o: acts.__setitem__("a", o))
            try:
                with torch.enable_grad():
                    out = m(x).float()[0]
                    outs.append(out.detach())
                    acts["a"].retain_grad()
                    target = out[0] if self.head == "reg" else corn_score(out) if self.head == "corn" else out[int(out.argmax())]
                    target.backward()
            finally:
                hook.remove()
            a, g = acts["a"][0].detach().float(), acts["a"].grad[0].float()
            cams.append(torch.relu((g.mean((1, 2))[:, None, None] * a).sum(0)).cpu().numpy())
        probs, pred, votes, score = self._summarise(outs)
        cam = square_to_image(np.mean(cams, 0), im, display_size)
        return probs.cpu().numpy(), pred, cam, votes.cpu().numpy(), score
