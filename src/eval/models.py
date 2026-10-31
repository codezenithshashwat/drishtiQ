"""Model specs the harness can evaluate. Each resolves to an object with .probs(im) and provenance metadata."""
import glob
import json
from pathlib import Path

from inference import CKPT, GRADER_HEADS, FrozenHeadGrader, V0Segmenter

from . import ROOT


def grader(spec, device=None):
    if spec == "v0":
        model = FrozenHeadGrader([CKPT / n for n in GRADER_HEADS], device)
        meta = dict(description="App v0: frozen ConvNeXt-T @224, 6 linear heads (3-fold CV x 2 seeds)",
                    train_data="IDRiD clean train 404 (3-fold CV heads)",
                    eval_overlap="YES: every val image was in the training folds of 4 of 6 heads (in-sample, optimistic)")
        return model, meta
    if spec.startswith("frozen:"):
        paths = sorted(glob.glob(str(ROOT / spec.removeprefix("frozen:"))))
        if not paths:
            raise SystemExit(f"No checkpoints match {spec}")
        sidecar = Path(paths[0]).with_suffix(".json")
        info = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        model = FrozenHeadGrader(paths, device)
        meta = dict(description=info.get("description", f"Frozen ConvNeXt-T heads x{len(paths)}"),
                    train_data=info.get("train_data", "unknown"), eval_overlap=info.get("eval_overlap", "unknown"))
        return model, meta
    if spec.startswith("finetune:"):
        from inference.finetuned import FinetunedGrader
        paths = sorted(glob.glob(str(ROOT / spec.removeprefix("finetune:"))))
        if not paths:
            raise SystemExit(f"No checkpoints match {spec}")
        info = json.loads(Path(paths[0]).with_suffix(".json").read_text())
        model = FinetunedGrader(paths, device)
        meta = dict(description=info["description"] + (f", {len(paths)}-seed ensemble" if len(paths) > 1 else ""),
                    train_data=info["train_data"], eval_overlap=info["eval_overlap"])
        return model, meta
    if spec.startswith("feathead:"):
        from inference.feature_head import FeatureHeadGrader
        paths = sorted(glob.glob(str(ROOT / spec.removeprefix("feathead:"))))
        if not paths:
            raise SystemExit(f"No checkpoints match {spec}")
        info = json.loads(Path(paths[0]).with_suffix(".json").read_text())
        model = FeatureHeadGrader(paths, device)
        meta = dict(description=info["description"] + f", {len(paths)}-seed ensemble", train_data=info["train_data"],
                    eval_overlap=info["eval_overlap"])
        return model, meta
    raise SystemExit(f"Unknown grader spec {spec!r}; use 'v0', 'frozen:<glob>', 'finetune:<glob>' or 'feathead:<glob>' (relative to project root)")


def segmenter(spec, device=None):
    if spec == "v0":
        model = V0Segmenter(device)
        meta = dict(description="App v0: SegFormer-B0 @512 (HE/EX/SE) + MA-only U-Net @512",
                    train_data="IDRiD segmentation dev-train (40 images)", eval_overlap="no")
        return model, meta
    if spec.split(":")[0] in ("a3", "a3tta", "a3ens"):
        from inference import default_device
        from inference.a3_segmenter import A3Segmenter, paths_for
        from inference.pipeline import MEAN, STD
        paths, _ = paths_for(spec)
        info = json.loads(Path(paths[0]).with_suffix(".json").read_text())
        model = A3Segmenter.from_spec(spec, device or default_device(), MEAN, STD)
        extra = f"; {len(paths)}-model ensemble" if len(paths) > 1 else ""
        extra += "; flip TTA" if model.tta else ""
        return model, dict(description=info["description"] + extra, train_data=info["train_data"], eval_overlap=info["eval_overlap"])
    raise SystemExit(f"Unknown segmenter spec {spec!r}; use 'v0', 'a3:<ckpt>', 'a3tta:<ckpt>' or 'a3ens:<glob>'")
