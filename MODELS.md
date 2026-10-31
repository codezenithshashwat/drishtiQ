# Models

Weights are not committed. Hosting location is **to be decided** (options: GitHub Release assets, Hugging Face model repo, or Git LFS).

| Model | File (under `models/checkpoints/`) | Size | Used by |
|---|---|---|---|
| Grader v0: ConvNeXt-Tiny frozen features + 6 linear heads (3 folds × 2 seeds) | `model_selection/frozen_convnext_tiny_r224_baseline_f{0,1,2}_s{17,29}.pt` | ~24 KB each | App v0 |
| Backbone for grader v0 | torchvision `convnext_tiny-983f1562.pth` (downloaded automatically into `models/pretrained/`) | 109 MB | App v0 |
| Lesion segmentation v0 (HE/EX/SE) | `model_selection/seg_Segformer_full512_bce_dice_s17.pt` | 13 MB | App v0 |
| MA segmentation v0 | `model_selection/ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.pt` | 48 MB | App v0 |

## Pretrained foundation weights (not used by the app yet)

| Model | Source | File | SHA-256 | Load check |
|---|---|---|---|---|
| RETFound MAE, colour fundus | Hugging Face `YukunZhou/RETFound_mae_natureCFP` @ `556830f78214f0e8da35af965292ac5a3180ac47` (gated: request access, then `hf auth login`) | `RETFound_mae_natureCFP.pth`, 3,952,489,221 bytes (encoder + MAE decoder + optimizer state) | `e1e4f66a1b792eeb6e2efaf158f33be35c8255f36b3d17ed67cd5129da246485` (matches the HF LFS hash) | `src/models/check_retfound.py`: ViT-L/16 (303.3 M encoder params) loads with only `fc_norm.*` and `head.*` missing, as expected; no unexpected keys |

Download location: `models/pretrained/huggingface/hub/` (set `HF_HUB_CACHE`, not `HF_HOME`, so the stored login token is still found).

## Phase 1 checkpoints

| Family | Folder | Produced by |
|---|---|---|
| Frozen-head baseline (dev-train only) | `models/checkpoints/phase1/frozen_convnext224_devtrain_v1_s{17,29,41}.pt` | `src/train/frozen_head.py` |
| Segmentation 5-fold CV models | `models/checkpoints/phase1/segcv/` | `src/train/seg_cv.py` |
| Fine-tuned graders | `models/checkpoints/phase1/graders/` (+ `.json` config per checkpoint) | `src/train/finetune_grader.py` |
| Kaggle outputs | `checkpoints/kaggle/<run>/` | Kaggle notebooks in `notebooks/kaggle/` |

New checkpoints are versioned (never overwritten) and recorded with their SHA-256 in `results/registry.csv`.
`GET /api/version` reports the SHA-256 of every loaded checkpoint.
