"""Frozen feature backbones for linear-probe graders, with one shared input transform.

Both backbones receive the same input: field-of-view crop, square resize, ImageNet normalisation.
  convnext_tiny_in1k  torchvision ConvNeXt-Tiny ImageNet-1k, 768-d pooled features
  retfound_cfp        RETFound MAE colour-fundus ViT-L/16, 1024-d: mean of the pretrained-norm'd patch tokens
"""
import os
from pathlib import Path

import numpy as np
import torch

from .pipeline import MEAN, STD, ROOT
from .preprocess import crop_to_fov

RETFOUND = ("YukunZhou/RETFound_mae_natureCFP", "556830f78214f0e8da35af965292ac5a3180ac47", "RETFound_mae_natureCFP.pth")


def fovcrop(im, size):
    from PIL import Image
    return np.asarray(crop_to_fov(im).resize((size, size), Image.Resampling.BILINEAR), np.uint8)


def normalise(batch_uint8, device):
    x = torch.from_numpy(np.ascontiguousarray(batch_uint8)).to(device).permute(0, 3, 1, 2).float() / 255
    return (x - torch.tensor(MEAN, device=device).view(1, 3, 1, 1)) / torch.tensor(STD, device=device).view(1, 3, 1, 1)


class Backbone(torch.nn.Module):
    def __init__(self, name, device):
        super().__init__()
        self.name, self.device = name, device
        if name == "convnext_tiny_in1k":
            from torchvision import models
            m = models.convnext_tiny(weights=models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1)
            m.classifier[-1] = torch.nn.Identity()
            self.dim, self.half = 768, False
        elif name in ("retfound_cfp", "retfound_cfp_officialpool"):
            import timm
            from huggingface_hub import hf_hub_download
            os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "models/pretrained/huggingface/hub"))
            path = hf_hub_download(RETFOUND[0], RETFOUND[2], revision=RETFOUND[1])
            state = {k: v for k, v in torch.load(path, map_location="cpu", weights_only=False)["model"].items()
                     if not k.startswith(("decoder", "mask_token"))}
            if name == "retfound_cfp":
                # Pretrained `norm` on every token, then mean of patch tokens (first A1 probe).
                m = timm.create_model("vit_large_patch16_224", pretrained=False, num_classes=0, global_pool="avg", fc_norm=False)
                expected_missing = []
            else:
                # Official RETFound global pooling (models_vit.py): mean of raw patch tokens, then a fresh
                # LayerNorm (fc_norm, eps 1e-6); the pretrained `norm` is deleted.
                m = timm.create_model("vit_large_patch16_224", pretrained=False, num_classes=0, global_pool="avg", fc_norm=True)
                state = {k: v for k, v in state.items() if not k.startswith("norm.")}
                expected_missing = ["fc_norm.weight", "fc_norm.bias"]
            missing, unexpected = m.load_state_dict(state, strict=False)
            assert sorted(missing) == sorted(expected_missing) and not unexpected, (missing, unexpected)
            self.dim, self.half = 1024, device == "cuda"
        else:
            raise ValueError(name)
        m.requires_grad_(False)
        self.model = (m.half() if self.half else m).to(device).eval()

    @torch.no_grad()
    def forward(self, batch_uint8):
        x = normalise(batch_uint8, self.device)
        return self.model(x.half() if self.half else x).float()


def cached_inputs(split_rows, key, size, cache_dir):
    """uint8 (n, size, size, 3) FOV-crop inputs for a split, cached on disk."""
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image, ImageOps
    path = Path(cache_dir) / f"fovcrop{size}_{key}.npy"
    if path.exists():
        return np.load(path)

    def load(r):
        with Image.open(ROOT / r["filepath"]) as im:
            return fovcrop(ImageOps.exif_transpose(im).convert("RGB"), size)
    with ThreadPoolExecutor(8) as ex:
        arr = np.stack(list(ex.map(load, split_rows)))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return arr
