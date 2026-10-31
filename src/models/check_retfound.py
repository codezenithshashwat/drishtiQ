"""Verify the RETFound CFP checkpoint: SHA-256 against the Hugging Face LFS hash, and a load into a ViT-Large/16.

RETFound fine-tuning uses global average pooling with fc_norm and a new head, so loading the MAE encoder is expected
to leave `head.*` and `fc_norm.*` missing. Decoder / mask-token / final `norm.*` keys are dropped as unused.
    .venv\\Scripts\\python src\\models\\check_retfound.py
"""
import hashlib
import json
from pathlib import Path

import timm
import torch

ROOT = Path(__file__).resolve().parents[2]
REPO, REVISION = "YukunZhou/RETFound_mae_natureCFP", "556830f78214f0e8da35af965292ac5a3180ac47"
LFS_SHA256 = "e1e4f66a1b792eeb6e2efaf158f33be35c8255f36b3d17ed67cd5129da246485"


def main():
    snap = ROOT / "models/pretrained/huggingface/hub/models--YukunZhou--RETFound_mae_natureCFP/snapshots" / REVISION
    path = snap / "RETFound_mae_natureCFP.pth"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    digest = h.hexdigest()
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    state = ckpt.get("model", ckpt)
    model = timm.create_model("vit_large_patch16_224", pretrained=False, num_classes=5, global_pool="avg", drop_path_rate=0.2)
    dropped = [k for k in state if k.startswith(("decoder", "mask_token")) or k.startswith("norm.")]
    encoder = {k: v for k, v in state.items() if k not in dropped}
    result = model.load_state_dict(encoder, strict=False)
    with torch.no_grad():
        out = model(torch.zeros(1, 3, 224, 224))
    report = dict(repo=REPO, revision=REVISION, file=path.name, bytes=path.stat().st_size, sha256=digest,
                  sha256_matches_hf_lfs=digest == LFS_SHA256, checkpoint_top_keys=list(ckpt) if isinstance(ckpt, dict) else None,
                  state_keys=len(state), dropped_unused=len(dropped), dropped_prefixes=sorted({k.split(".")[0] for k in dropped}),
                  missing_keys=result.missing_keys, unexpected_keys=result.unexpected_keys,
                  encoder_params_m=round(sum(p.numel() for n, p in model.named_parameters() if not n.startswith(("head", "fc_norm"))) / 1e6, 1),
                  forward_output_shape=list(out.shape))
    out_path = ROOT / "results/audit/retfound_check.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
