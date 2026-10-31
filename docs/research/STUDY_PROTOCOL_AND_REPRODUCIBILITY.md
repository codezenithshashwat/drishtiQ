# Study protocol and reproducibility notes

This is a staged development study, not a final system build. Grading uses only the 404-row clean training manifest. No final 404-image fit, clean-test evaluation, external validation or multi-task training is authorized by this runner. Patient-level independence remains unknown.

## How to interpret the experiments

A pretrained backbone supplies image features learned from ImageNet. A frozen-feature experiment trains only a small five-grade classifier; partial fine-tuning subsequently permits the last backbone stage to change. Frozen BatchNorm statistics and disabled classifier stochastic layers make small-batch grading comparisons more stable. Different ImageNet training recipes remain an unavoidable package-level confound. Frozen features are standardized using the training fold only; the resulting transform is algebraically absorbed into the head before fine-tuning, preserving its starting predictions.

Each architecture has the same three stratified image folds and optimization seeds 17 and 29. The minority training grade has only 18 images, so each validation fold contains six such images. Frozen-head fits use AdamW, up to 60 epochs, patience 12, and validation macro-F1 then QWK to choose a checkpoint. All four families receive a common six-epoch partial-tuning screen on fold 0 with both seeds; two finalists continue on folds 1 and 2. A partial fit may retain the initial frozen-head checkpoint if fine-tuning does not improve validation. This is recorded as best_epoch=-1, rather than presented as successful adaptation.

Partial fine-tuning uses AdamW with backbone LR 1e-4, head LR 1e-3, weight decay 1e-4, mixed precision and gradient clipping at norm 5. Its target effective batch is 16, with microbatches 4 at 224/384, 2 at 512 and 1 at 768. Incomplete final accumulation groups are included, so the last update has fewer examples. Microbatch and effective-batch values are recorded in each run. Latencies must be interpreted with their batch size. Grading image caches use bilinear long-side resizing and square black padding; an input size is the active long side, not a square distortion of the photograph.

The resolution screen is restricted to the shortlisted backbone. One-factor screens compare border cropping, minimal augmentation, moderate augmentation, weighted CE, focal loss and an ordinal penalty against the same baseline. Minimal augmentation is a 50% horizontal flip. Moderate augmentation adds a 50% vertical flip, a uniformly sampled ±10-degree rotation using the installed torchvision default nearest interpolation, and a brightness multiplier in [0.9,1.1]. There is no random crop, elastic warp, CLAHE or contrast enhancement. Do not infer the benefit of an untested stack from individually favorable transformations.

Weighted CE uses inverse training-fold class frequency N/(5*n_class), never validation frequency. Focal uses gamma=2 without an additional alpha term. The ordinal objective is CE plus the mean squared gap between the predicted and one-hot target cumulative distributions at four grade thresholds, coefficient 1. Equal ordinal spacing is a mathematical convention, not a clinical harm scale. The reported grade3/4-to0/1 error bin is not a referral rule.

## Segmentation design

Fifty eligible organizer training photographs remain after conservatively excluding four candidate correspondences to grading test images. They are split once into 40 training and 10 validation photographs, stratifying soft-exudate annotation availability. No original photograph contributes patches to both roles. Exact underlying patient identity is unavailable; unresolved correspondences may conceal other dependencies. Grading and segmentation models never share learned weights or automatically propagated labels.

The four output channels are MA, HE, EX and SE, with separate sigmoid probabilities. OD is anatomy and is not allowed to inflate lesion metrics. A missing annotation is unavailable supervision: its validity flag is false and its channel contributes neither loss nor metric. Palette indices encode foreground; an RGBA mask is interpreted through RGB only, excluding alpha. A background patch within a supplied annotation is different from an absent annotation.

U-Net, U-Net++ and DeepLabV3+ use the same pretrained ResNet18 encoder; SegFormer uses pretrained MiT-B0. Decoder widths are bounded for 4 GB VRAM. This is a model-package comparison, not a proof that a decoder alone causes a difference. All segmentation parameters are trainable; BatchNorm running statistics are fixed consistently because DeepLab's global pooling branch cannot update BatchNorm from batch1. This engineering choice can affect decoder learning and must be revisited under a larger-batch study.

All segmentation runs have six epochs and a fixed final-epoch checkpoint. Each original training image contributes either two full512 views, eight native256 patches (batch4), or two native512 patches (batch1) per epoch. This matches nominal input-pixel budgets and update counts; supervised pixel counts differ because letterbox padding is excluded. Every mode has horizontal flips. Half of training patches are centered near a lesion pixel, choosing an available lesion type uniformly; the rest are uniform spatial samples. This uses training masks only. Validation reconstructs **every native pixel** with nonoverlapping tiles, without selecting lesion-rich validation patches. Full-image predictions are unpadded and interpolated to the same native grid. Boundary effects and lost patch context remain limitations.

The statement above describes the initial four-lesion suite. After its MA failures, a separate, explicitly adaptive four-fit MA-only follow-up was added: one existing U-Net/ResNet18 family, full512 versus native256, two seeds, twelve epochs for both modes. It uses an MA head only, MA-centered positive sampling and 0.5 weighted BCE + 0.5 Tversky (FP coefficient .3, FN .7, smoothing 1). The positive weight is min(50, native training negative/positive ratio); no validation prevalence or official test information sets it. These coefficients are engineering hypotheses motivated by sparse foreground and the Tversky literature, not calibrated clinical costs. Comparing full versus patch **within this suite** is meaningful; comparing its MA-only Dice to the initial suite's four-lesion mean as if it were one isolated change is not. This extension is recorded in adaptive_MA_amendment.json and is not retrospectively called preregistered.

The threshold is fixed at 0.5. Dice, IoU, recall and precision are recorded per available lesion and image, then aggregated. Component detection uses one-to-one eight-connected region matching at IoU >= 0.1. These regions are annotation components, not independently adjudicated biological lesions. Native validation cost includes tiling and component analysis; it is not just a GPU forward-pass timer.

## Staging and documented changes

The initial plan is saved in configs/experiments/model_selection_preregistered.json. It is not a registered clinical study. Run configurations preserve what was executed; model-selection CV still has selection optimism. The adaptive confirmation amendment, if present, explicitly adds matched selected-resolution CE and 512 CE confirmation on the other folds because macro-F1, ordinal agreement and MA sampling preservation do not give identical rankings. It is labeled an adaptive amendment, not retrospectively called preregistered. No test result informs it.

After CV, an engineering tie-break was recorded: within the already declared macro-F1/QWK tolerance band, a same-backbone head-only fit is preferred to updating millions of extra parameters for a tiny improvement. It is a transparent post-CV judgment, not a preregistered statistical equivalence or clinical noninferiority claim.

One exploratory MA patch run under FP16 developed NaN training loss. Its original empty-mask score was invalidated, preserved and excluded from primary comparison. The complete matched MA-only suite was rerun in FP32 with finite loss/logit/gradient checks. Initial four-lesion checkpoints were re-evaluated using finite-checked FP32 probabilities before thresholding, without retraining or changing their weights; their original AMP summaries are retained separately. A numerical failure must never silently become an apparently valid all-background prediction. Failure and recovery are recorded, not hidden. Only the matched FP32 MA-only suite is ranked; the original AMP probes are separate exploratory artifacts.

A metadata test initially exposed pandas string identifiers stored as object arrays in feature caches. They were converted to plain Unicode strings. Numeric feature arrays were checked by SHA-256 before and after and did not change. The evidence is in feature_metadata_validation_fix.json. This was a cache-metadata fix, not a feature, label or model-result alteration. The final protocol tests cover metadata order as well as fold separation, unavailable-mask gradients, alpha exclusion, ordinal distance and the head-standardization algebra. Synthetic filesystem audit events verify test-read/raw-write blocking without actually opening a test file or writing a probe into raw.

## Data protection and reproduction

Each process checks all raw path/size/modification-time values against the completed integrity-stage snapshot before starting and after finishing. Reading test pixels to rehash them is deliberately avoided during selection. The process audit hook denies raw writes and raw reads outside explicitly registered development image/mask paths, and denies opening the clean test manifest. Thus test protection covers the runner's file paths, while uncertain re-encoded cross-task identities remain a disclosed limitation. Access timestamps are not part of immutability checks.

Development-input checksums are locked. Caches/checkpoints must not silently resume under changed manifests, annotation policies or cross-task mappings. Checkpoint configs, predictions, histories, source hashes, package versions and device information are preserved. Pretrained weights are stored under models/pretrained; training checkpoints under models/checkpoints/model_selection. The existing .gitignore excludes raw/interim/processed data and checkpoints.

Use requirements-model-selection.txt; the full installed environment is recorded in outputs/metrics/model_selection/environment_freeze.txt. From the project root, run:

```powershell
.venv\Scripts\python.exe src\model_selection\literature.py
.venv\Scripts\python.exe src\model_selection\run_study.py --stage pilot
.venv\Scripts\python.exe src\model_selection\run_study.py --stage grading
.venv\Scripts\python.exe src\model_selection\run_study.py --stage ablations
.venv\Scripts\python.exe src\model_selection\run_study.py --stage confirmation
.venv\Scripts\python.exe src\model_selection\run_study.py --stage segmentation
.venv\Scripts\python.exe src\model_selection\run_study.py --stage ma_specialist
.venv\Scripts\python.exe src\model_selection\run_study.py --stage recheck_segmentation
.venv\Scripts\python.exe src\model_selection\test_protocol.py
.venv\Scripts\python.exe src\model_selection\run_study.py --stage report
.venv\Scripts\python.exe src\model_selection\validate_study.py
```

Completed runs resume; this is not an independent repeat of their numeric results. To reproduce a fit on changed hardware or libraries, preserve the original artifacts and use a separate output root rather than overwriting evidence. Bit-identical GPU results across environments are not promised. No external-generalization, calibration or clinical-validity claim is supported until separately evaluated.

## Final numerical scoring and verification

Saved float32 probabilities can accumulate tiny row-sum errors when reopened as float64 CSV values. Final scoring therefore uses finite-checked float64 probabilities, renormalizes only within numerical tolerance, and uses an explicit 1e-12 probability floor for NLL. This is numerical scoring consistency, not fitted calibration. All 82 grading fits were rescored from preserved predictions; hard predictions, accuracy, macro-F1 and QWK were verified unchanged. Original metric records are preserved alongside the standardized records. Epoch histories retain their original in-training NLL definition; final scorecard NLL uses the standardized definition. Evidence is in numeric_scoring_standardization.csv.

Final verification recorded 320 passing checks, eight passing protocol tests, 40 readable figures, and zero test evaluations. Twenty segmentation fits are validated for primary comparisons; four earlier AMP MA probes are unranked, including one explicitly excluded numerical failure. The 82 grading fits include inexpensive frozen-head warm-ups and repeated folds/seeds; they do not represent 82 different architecture families. Patient independence and external generalization remain unverified.
