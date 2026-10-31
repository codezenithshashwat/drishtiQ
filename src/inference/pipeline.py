"""Single-image inference: quality checks, DR grading, Grad-CAM, lesion segmentation.

v0.1 prototype: reuses the development checkpoints from the model-selection study.
- Grader: frozen ImageNet ConvNeXt-Tiny @224 + six linear heads (3 folds x 2 seeds), probabilities averaged.
- Lesions: SegFormer-B0 @512 for HE/EX/SE; MA-only U-Net @512 for MA, followed by the post-processing in
  configs/postprocess/pp_v2.json (per-lesion thresholds, optic-disc masking for MA/EX, component-area filters),
  selected by 5-fold cross-validation (see docs/research/ARCHITECTURE_DECISION_LOG.md, ADR-011).
None of these models is calibrated or externally validated; the API says so in every response.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
# Only the download cache is redirected (not HF_HOME), so a stored Hugging Face login token is still found.
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "models/pretrained/huggingface/hub"))
torch.hub.set_dir(str(ROOT / "models/pretrained"))

import segmentation_models_pytorch as smp  # noqa: E402  (HF_HUB_CACHE must be set first)
from torchvision import models  # noqa: E402

from . import explanations, findings, landmarks  # noqa: E402
from . import postprocess as pp  # noqa: E402

QUALITY_LIMITS = dict(min_brightness=25, max_brightness=200, min_sharpness=0.5)
# Fundus photographs have a round field on a dark surround, so their corners are dark. The minimum corner darkness was
# fitted on training-side fundus images (R2, ADR-023; tools/fit_quality_gate.py). Without the file the check is off.
QUALITY_CONFIG = ROOT / "configs/quality/quality_v1.json"
CORNER_DARK_MIN = json.loads(QUALITY_CONFIG.read_text())["corner_dark_min"] if QUALITY_CONFIG.exists() else None


def corner_dark(fov):
    """Fraction of dark pixels in the four corner squares (side 8% of the shorter image side)."""
    k = max(4, round(0.08 * min(fov.shape)))
    corners = np.concatenate([fov[:k, :k].ravel(), fov[:k, -k:].ravel(), fov[-k:, :k].ravel(), fov[-k:, -k:].ravel()])
    return float(1 - corners.mean())


def quality_flags(quality):
    """Structured flags (with trigger values) for the heuristic image checks."""
    flags = []
    if quality.get("brightness") is not None and quality["brightness"] < QUALITY_LIMITS["min_brightness"]:
        flags.append(dict(id="dark", trigger=dict(brightness=round(quality["brightness"], 1)),
                          simple="The photo is too dark to judge well.",
                          template="The image is very dark: mean green level {brightness} (threshold 25)."))
    if quality.get("brightness") is not None and quality["brightness"] > QUALITY_LIMITS["max_brightness"]:
        flags.append(dict(id="bright", trigger=dict(brightness=round(quality["brightness"], 1)),
                          simple="The photo is too bright to judge well.",
                          template="The image is very bright: mean green level {brightness} (threshold 200)."))
    if quality.get("sharpness") is not None and quality["sharpness"] < QUALITY_LIMITS["min_sharpness"]:
        flags.append(dict(id="blur", trigger=dict(sharpness=round(quality["sharpness"], 2)),
                          simple="The photo looks blurry. Small spots may be missed.",
                          template="The image looks blurred: sharpness {sharpness} (threshold 0.50); small lesions may be missed."))
    if CORNER_DARK_MIN is not None and quality.get("corner_dark") is not None and quality["corner_dark"] < CORNER_DARK_MIN:
        flags.append(dict(id="not-fundus", trigger=dict(corner_dark=round(quality["corner_dark"], 2)),
                          simple="This may not be an eye photo. A person should check it.",
                          template="No dark border around a round retinal field (corner darkness {corner_dark}); this may not be a fundus photograph."))
    if quality.get("red_dominant") is False:
        flags.append(dict(id="colour", trigger={}, simple="The colours look unusual for an eye photo.", template="The colour distribution is atypical for a colour fundus photograph."))
    return flags

CKPT = ROOT / "models/checkpoints/model_selection"
GRADER_HEADS = [f"frozen_convnext_tiny_r224_baseline_f{f}_s{s}.pt" for f in range(3) for s in (17, 29)]
SEG_FOUR = "seg_Segformer_full512_bce_dice_s17.pt"
SEG_MA = "ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.pt"

GRADES = ["No apparent DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
LESIONS = ["MA", "HE", "EX", "SE"]
LESION_NAMES = {"MA": "Microaneurysms", "HE": "Haemorrhages", "EX": "Hard exudates", "SE": "Soft exudates"}
# Lesion overlay colours come from the single token source (Okabe-Ito, distinct from the severity scale).
_TOKENS = json.loads((ROOT / "design/tokens.json").read_text(encoding="utf-8"))
LESION_RGB = {k: tuple(int(_TOKENS["color"]["lesion"][k][i:i + 2], 16) for i in (1, 3, 5)) for k in ("MA", "HE", "EX", "SE")}
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
DISPLAY = 1024
POSTPROCESS = ROOT / "configs/postprocess/pp_v2.json"
# The app's grader is chosen here; a swap (see the decision log) only edits this file.
APP_CONFIG = ROOT / "configs/app/app.json"
MODEL_VERSION = json.loads(APP_CONFIG.read_text())["version"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def letterbox(im, size, resample=Image.Resampling.BILINEAR):
    """Aspect-preserving resize with centred black padding; matches the training-time transform."""
    w, h = im.size
    scale = size / max(w, h)
    nw, nh = round(w * scale), round(h * scale)
    left, top = (size - nw) // 2, (size - nh) // 2
    out = ImageOps.expand(im.resize((nw, nh), resample), (left, top, size - nw - left, size - nh - top), fill=0)
    return out, (left, top, nw, nh)


def to_tensor(im, device):
    x = (np.asarray(im, np.float32) / 255 - MEAN) / STD
    return torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(device)


def png_b64(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def jpeg_b64(im):
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def crop_back(prob_map, box, out_size):
    """Remove letterbox padding from a model-resolution map and resize it to the display image."""
    left, top, nw, nh = box
    region = prob_map[top:top + nh, left:left + nw]
    return np.asarray(Image.fromarray(region.astype(np.float32), mode="F").resize(out_size, Image.Resampling.BILINEAR))


def default_device():
    # RS_DEVICE=cpu runs on the CPU with the GPU still visible to the driver. Hiding the GPU (CUDA_VISIBLE_DEVICES=-1) is
    # unstable on Windows with this NVIDIA driver: any CUDA driver initialisation (an is_available() probe, or the autograd
    # engine during Grad-CAM's backward pass) finds no device, unloads nvdxgdmal64.dll and leaves a callback that later
    # crashes the process (access violation; ADR-044). The probe is still skipped when the GPU is hidden.
    forced = os.environ.get("RS_DEVICE", "").strip().lower()
    if forced in ("cpu", "cuda"):
        return forced
    if os.environ.get("CUDA_VISIBLE_DEVICES", "").strip() == "-1":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def convnext_backbone(device):
    """ImageNet ConvNeXt-Tiny returning 768-d pooled features; weights frozen."""
    backbone = models.convnext_tiny(weights=models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1)
    backbone.classifier[-1] = torch.nn.Identity()
    backbone.requires_grad_(False)  # Grad-CAM needs activation gradients only
    return backbone.to(device).eval()


class FrozenHeadGrader:
    """Frozen ImageNet ConvNeXt-Tiny @224 + an ensemble of standardised linear heads (probabilities averaged)."""

    def __init__(self, head_paths, device=None):
        self.device = device or default_device()
        self.backbone = convnext_backbone(self.device)
        self.checkpoints = {}
        heads, means, stds = [], [], []
        for path in map(Path, head_paths):
            c = torch.load(path, map_location="cpu", weights_only=True)
            heads.append(c["head"])
            means.append(c["feature_mean"])
            stds.append(c["feature_std"])
            self.checkpoints[path.name] = sha256(path)
        self.head_w = torch.stack([h["weight"] for h in heads]).float().to(self.device)  # (H,5,768)
        self.head_b = torch.stack([h["bias"] for h in heads]).float().to(self.device)  # (H,5)
        self.feat_mean = torch.stack(means).float().to(self.device)  # (H,768)
        self.feat_std = torch.stack(stds).float().to(self.device)

    def _logits(self, feat):
        z = (feat - self.feat_mean) / self.feat_std  # (H,768)
        return torch.einsum("hd,hkd->hk", z, self.head_w) + self.head_b  # (H,5)

    @torch.no_grad()
    def features(self, im):
        return self.backbone(to_tensor(letterbox(im, 224)[0], self.device))[0]

    @torch.no_grad()
    def probs(self, im):
        return self._logits(self.features(im)).softmax(1).mean(0).cpu().numpy()

    def grade_with_cam(self, im, display_size):
        """Returns (probabilities, grade, Grad-CAM on the display frame, per-head votes, continuous score=None)."""
        x224, box = letterbox(im, 224)
        x = to_tensor(x224, self.device).requires_grad_(True)
        acts = {}
        hook = self.backbone.features.register_forward_hook(lambda m, i, o: acts.__setitem__("a", o))
        try:
            with torch.enable_grad():
                logits = self._logits(self.backbone(x)[0])
                probs = logits.softmax(1).mean(0)
                pred = int(probs.argmax())
                acts["a"].retain_grad()
                logits[:, pred].mean().backward()
        finally:
            hook.remove()
        a, g = acts["a"][0], acts["a"].grad[0]  # (C,7,7)
        cam = torch.relu((g.mean((1, 2))[:, None, None] * a).sum(0)).detach().cpu().numpy()
        cam = np.asarray(Image.fromarray(cam.astype(np.float32), mode="F").resize((224, 224), Image.Resampling.BICUBIC))
        p = probs.detach().cpu().numpy()
        head_votes = logits.argmax(1).cpu().numpy()
        return p, pred, crop_back(cam, box, display_size), head_votes, None


class V0Segmenter:
    """SegFormer-B0 @512 for HE/EX/SE with its MA channel replaced by the MA-only U-Net @512."""

    def __init__(self, device=None):
        self.device = device or default_device()
        self.checkpoints = {}
        self.seg4 = smp.Segformer(encoder_name="mit_b0", encoder_weights=None, classes=4, decoder_segmentation_channels=128)
        self.seg4.load_state_dict(torch.load(CKPT / SEG_FOUR, map_location="cpu", weights_only=True))
        self.seg4 = self.seg4.to(self.device).eval()
        self.checkpoints[SEG_FOUR] = sha256(CKPT / SEG_FOUR)

        self.seg_ma = smp.Unet(encoder_name="resnet18", encoder_weights=None, classes=1, decoder_channels=(128, 64, 32, 16, 16))
        state = torch.load(CKPT / SEG_MA, map_location="cpu", weights_only=True)
        self.seg_ma.load_state_dict({k.removeprefix("net."): v for k, v in state.items()})
        self.seg_ma = self.seg_ma.to(self.device).eval()
        self.checkpoints[SEG_MA] = sha256(CKPT / SEG_MA)

    @torch.no_grad()
    def probs(self, im):
        """Returns (4,512,512) probabilities in MA,HE,EX,SE order and the letterbox box."""
        x512, box = letterbox(im, 512)
        x = to_tensor(x512, self.device)
        four = self.seg4(x).sigmoid()[0].cpu().numpy()
        four[0] = self.seg_ma(x).sigmoid()[0, 0].cpu().numpy()
        return four, box


def load_grader(spec, device):
    """'v0' (frozen ConvNeXt heads) or 'finetune:<glob relative to project root>' (fine-tuned seed ensemble)."""
    if spec == "v0":
        return FrozenHeadGrader([CKPT / name for name in GRADER_HEADS], device)
    if spec.startswith("finetune:"):
        import glob
        from .finetuned import FinetunedGrader
        paths = sorted(glob.glob(str(ROOT / spec.removeprefix("finetune:"))))
        if not paths:
            raise FileNotFoundError(spec)
        return FinetunedGrader(paths, device)
    raise ValueError(f"unknown grader spec {spec!r}")


class LesionSegmenter:
    """Per-lesion choice of segmentation model and post-processing, from configs/app/app.json "segmenter"
    ({lesion: {model, postprocess}}); without that key every lesion uses v0 + pp_v2. Swaps follow ADR-016."""

    def __init__(self, app, device):
        cfg = app.get("segmenter") or {k: dict(model="v0", postprocess=str(POSTPROCESS.relative_to(ROOT))) for k in LESIONS}
        self.models, self.params, self.spec, self.checkpoints = {}, {}, {}, {}
        for key in LESIONS:
            spec, pp_path = cfg[key]["model"], ROOT / cfg[key]["postprocess"]
            if spec not in self.models:
                if spec == "v0":
                    self.models[spec] = V0Segmenter(device)
                elif spec.split(":")[0] in ("a3", "a3tta", "a3ens"):
                    from .a3_segmenter import A3Segmenter
                    self.models[spec] = A3Segmenter.from_spec(spec, device, MEAN, STD)
                else:
                    raise ValueError(f"unknown segmenter spec {spec!r}")
                self.checkpoints.update(self.models[spec].checkpoints)
            config = json.loads(pp_path.read_text())
            self.params[key], self.spec[key] = {k: config[k] for k in pp.DEFAULT}, spec
            self.checkpoints[pp_path.name] = sha256(pp_path)

    def masks(self, im, size, od, lesions=LESIONS):
        """{lesion: (post-processed probability map, binary mask)} at display size, plus the FOV mask of the first lesion's
        post-processing (used for the field-of-view bounds)."""
        maps = {spec: self.models[spec].probs(im) for spec in {self.spec[k] for k in lesions}}
        fovs, out = {}, {}
        for key in lesions:
            params = self.params[key]
            e = params["fov_erode_frac"]
            if e not in fovs:
                fovs[e] = pp.fov_mask(im, size, e)
            seg, box = maps[self.spec[key]]
            prob = pp.masked_probs(crop_back(seg[LESIONS.index(key)], box, size), key, im, params, od=od, fov=fovs[e])
            out[key] = (prob, pp.binarize(prob, key, params, size[0]) & fovs[e])
        return out, fovs[self.params[lesions[0]]["fov_erode_frac"]]


class Pipeline:
    def __init__(self, device=None):
        self.device = device or default_device()
        app = json.loads(APP_CONFIG.read_text())
        self.grader_spec, self.model_version = app["grader"], app["version"]
        self.grader = load_grader(self.grader_spec, self.device)
        # Grading system parts (thresholds, specialists, TTA), each adopted by its own rule (ADR-033).
        self.system = None
        if any((app.get("system") or {}).values()):
            from .system import GradingSystem
            self.system = GradingSystem(app, self.grader, self.device)
        self.segmenter = LesionSegmenter(app, self.device)
        # A4 fusion (ADR-021) replaces the stage only when adopted by rule (app.json "fusion").
        self.fusion = None
        if app.get("fusion"):
            from .fusion import Fusion
            self.fusion = Fusion(ROOT / app["fusion"])
        self.checkpoints = {**self.grader.checkpoints, **self.segmenter.checkpoints}

    # ---- quality -------------------------------------------------------------------------
    @staticmethod
    def quality(im):
        """Heuristic image checks. These are proxies, not a validated gradability model."""
        small = np.asarray(im.resize((512, round(512 * im.height / im.width))), np.float32)
        fov = small.max(2) > 15
        fov_fraction = float(fov.mean())
        issues = []
        if fov_fraction < 0.2:
            issues.append("No circular retinal field detected; this may not be a fundus photograph.")
            return dict(usable=False, issues=issues, fov_fraction=fov_fraction, brightness=None, sharpness=None)
        inner = ndi.binary_erosion(fov, iterations=8)
        green = small[..., 1]
        brightness = float(green[fov].mean())
        sharpness = float(ndi.laplace(ndi.gaussian_filter(green, 1.0))[inner].var())
        red_dominant = small[..., 0][fov].mean() > small[..., 2][fov].mean()
        corners = corner_dark(fov)
        if CORNER_DARK_MIN is not None and corners < CORNER_DARK_MIN:
            issues.append("No dark border around a round retinal field; this may not be a fundus photograph.")
        if not red_dominant:
            issues.append("Colour distribution is atypical for a colour fundus photograph.")
        if brightness < 25:
            issues.append("Image is very dark (under-exposed).")
        elif brightness > 200:
            issues.append("Image is very bright (over-exposed).")
        if sharpness < 0.5:
            issues.append("Image appears blurred; small lesions may be missed.")
        return dict(usable=not issues, issues=issues, fov_fraction=fov_fraction, brightness=brightness, sharpness=sharpness,
                    red_dominant=bool(red_dominant), corner_dark=corners)

    # ---- full analysis --------------------------------------------------------------------
    def analyze(self, data: bytes):
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
        quality = self.quality(im)
        scale = DISPLAY / max(im.size)
        display = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.BILINEAR)
        result = dict(model_version=self.model_version, image=dict(width=im.width, height=im.height), quality=quality,
                      display_image=jpeg_b64(display))
        if quality["fov_fraction"] < 0.2:
            result["status"] = "rejected"
            return result

        probs, pred, cam, votes, score = self.grader.grade_with_cam(im, display.size)
        if self.system is not None and score is not None:
            score = self.system.score(im) if self.system.tta else score
            pred = self.system.stage(score, im)
            probs = np.zeros(5)
            probs[pred] = 1.0
        fov = np.asarray(display.convert("L"), np.float32) > 15
        cam = np.where(fov, cam, 0)
        cam = cam / cam.max() if cam.max() > 0 else cam
        # Cyan-to-white ramp: stays visible on orange fundus and distinct from the lesion palette.
        heat = np.zeros((*cam.shape, 4), np.uint8)
        heat[..., 0] = (255 * np.clip(2 * cam - 1, 0, 1)).astype(np.uint8)
        heat[..., 1] = (200 + 55 * cam).astype(np.uint8)
        heat[..., 2] = 255
        heat[..., 3] = (220 * np.clip((cam - 0.2) / 0.8, 0, 1)).astype(np.uint8)

        od = pp.locate_optic_disc(im)
        fov_landmark = landmarks.fovea(im, od)
        per_lesion, seg_fov = self.segmenter.masks(im, display.size, od)
        lesions, masks = [], {}
        for key in LESIONS:
            mask = per_lesion[key][1]
            masks[key] = mask
            labels, count = ndi.label(mask, np.ones((3, 3)))
            layer = np.zeros((*mask.shape, 4), np.uint8)
            layer[mask] = (*LESION_RGB[key], 230)
            # Dilate the outline of tiny components so they stay visible on screen.
            ring = ndi.binary_dilation(mask, iterations=3) & ~mask
            layer[ring] = (*LESION_RGB[key], 140)
            lesions.append(dict(key=key, name=LESION_NAMES[key], color="#%02x%02x%02x" % LESION_RGB[key],
                                components=int(count), area_percent_of_field=float(100 * mask.sum() / max(fov.sum(), 1)),
                                overlay=png_b64(layer)))

        if self.fusion is not None and score is not None:
            from .fusion import features
            probs = self.fusion.probs(features(score, masks, seg_fov))
            pred = int(np.argmax(probs))
        referable_p = float(probs[2:].sum())
        top = float(probs.max())
        agreement = float((votes == pred).mean())
        # Regression graders: confidence = distance of the continuous score to the nearest grade threshold.
        margin = float(np.min(np.abs(self.grader.thresholds - score))) if score is not None else None
        uncertain_score = margin < 0.25 if margin is not None else top < 0.5
        low_confidence = uncertain_score or agreement < 0.67
        n_regions = {l["key"]: l["components"] for l in lesions}
        flags = quality_flags(quality)
        if low_confidence:
            heads, agreeing = len(votes), int((votes == pred).sum())
            needed = int(np.ceil(0.67 * heads))
            reasons, trigger = [], {}
            if uncertain_score and margin is not None:
                reasons.append("the grade score {score} is only {margin} from a grade boundary (0.25 needed)")
                trigger.update(score=round(score, 2), margin=round(margin, 2))
            elif uncertain_score:
                reasons.append("the top grade score is {top_score}, below 0.50")
                trigger["top_score"] = round(top, 2)
            if agreement < 0.67:
                reasons.append("only {agreeing} of {heads} ensemble heads agree ({needed} needed)")
                trigger.update(agreeing=agreeing, heads=heads, needed=needed)
            flags.append(dict(id="low-confidence", trigger=trigger, simple="Low confidence: needs a doctor's look.",
                              template="Model confidence is low: " + " and ".join(reasons) + ". Clinician review recommended."))
        if pred >= 1 and not sum(n_regions.values()):
            flags.append(dict(id="grade-without-lesions", trigger=dict(regions=0), refs={"lesions": LESIONS},
                              simple="A stage was given, but no spots were found. A doctor should look.",
                              template="The grade suggests DR but {regions} lesion regions were segmented; review the image directly."))
        if pred == 0 and n_regions["HE"] + n_regions["EX"] + n_regions["SE"] >= 3:
            flags.append(dict(id="lesions-without-grade", trigger=dict(regions=n_regions["HE"] + n_regions["EX"] + n_regions["SE"]),
                              refs={"lesions": ["HE", "EX", "SE"]},
                              simple="Stage 0 was given, but {regions} bleeding spots or deposits were found. A doctor should look.",
                              template="The grade suggests no DR but {regions} haemorrhage/exudate regions were segmented "
                                       "(threshold 3); review recommended."))

        fov_cols = np.flatnonzero(seg_fov.any(0))
        fov_rows = np.flatnonzero(seg_fov.any(1))
        fov_centre = ((fov_cols.min() + fov_cols.max()) / 2, (fov_rows.min() + fov_rows.max()) / 2) if len(fov_cols) else (display.width / 2, display.height / 2)
        grading = dict(grade=pred, label=GRADES[pred], probabilities=[round(float(v), 4) for v in probs],
                       referable_probability=round(referable_p, 4), head_agreement=round(agreement, 4), low_confidence=low_confidence,
                       calibrated=False, grader=self.grader_spec, fused=self.fusion is not None,
                       score=None if score is None else round(score, 3),
                       thresholds=None if score is None else [round(float(t), 3) for t in self.grader.thresholds])
        if score is not None:
            # Plain-language position: the two stages the score lies between, via the nearest grade boundary.
            t = self.grader.thresholds
            i = int(np.argmin(np.abs(t - score)))
            grading["between"] = dict(lower=i, upper=i + 1, closer_to=pred, nearest_boundary=i)
        record = findings.build(
            grading, masks, LESION_NAMES, {k: quality[k] for k in ("usable", "fov_fraction", "brightness", "sharpness")},
            od_display=(od[0] * scale, od[1] * scale, od[2] * scale),
            fovea_display=(fov_landmark["x"] * scale, fov_landmark["y"] * scale), fovea_uncertain=fov_landmark["uncertain"],
            fov_centre=fov_centre, versions=dict(app=self.model_version, grader=self.grader_spec, checkpoints=self.checkpoints), flags=flags)

        if low_confidence or not quality["usable"]:
            recommendation = "Insufficient confidence: clinician review recommended."
        elif pred >= 2:
            recommendation = "Referable diabetic retinopathy suspected: refer to an ophthalmologist."
        elif pred == 1:
            recommendation = "Mild NPDR suspected: re-screen per local protocol; clinician to confirm."
        else:
            recommendation = "No apparent DR detected: routine re-screening per local protocol; clinician to confirm."

        result.update(
            status="ok",
            grading=grading,
            attribution=dict(method="Grad-CAM (ConvNeXt last stage)", overlay=png_b64(heat),
                             note="Shows image regions that most influenced the grade. It is not a lesion map."),
            lesions=lesions,
            consistency_flags=[f["id"] for f in flags],
            findings=record,
            explanations=explanations.explain(record),
            recommendation=recommendation,
            disclaimer=("Research prototype for screening decision support only. Not a diagnosis and not validated for "
                        "clinical use. Probabilities are uncalibrated. A qualified clinician makes the final decision."),
        )
        return result


