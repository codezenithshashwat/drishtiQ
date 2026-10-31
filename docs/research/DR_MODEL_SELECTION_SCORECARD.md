# DR model-selection scorecard

This is a **bounded development study**, not clinical validation or a final clean-test result. Only the clean 404-image development manifest was used for grading; the 102-image clean test manifest and its pixels were blocked by the runner. Official segmentation test images were also blocked. No joint grading/segmentation model was trained. Patient independence remains unknown.

Hardware: NVIDIA GeForce RTX 3050 A Laptop GPU, 4.00 GiB VRAM; 2.11.0+cu128. Each fit records a configuration and checkpoint. Frozen features: three stratified folds × two seeds; each validation fold contains only six grade-1 images. All four grading architectures received the same common screen. Only two finalists received complete partial-tuning CV. Resolution and one-factor screens use fold0/two seeds before matched confirmation. Fold/seed spread is descriptive; six scores are correlated, not six independent clinical studies.

## Common grading screen: equal fold, seeds, resolution and objective

| architecture | runs | macro_f1 | qwk | grade1_recall | undergrading | parameters | trainable_parameters | peak_MiB | inference_s_per_cached_image | checkpoint_MiB | explanation_tooling_compatibility | external_validation_evidence | resolution_evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| convnext_tiny | 2 | 0.51937 | 0.81003 | 0.0 | 0.0122 | 27823973.0 | 15475973.0 | 362.42676 | 0.00294 | 106.21086 | Grad-CAM compatible; fidelity untested | none locally; independent evaluation required | 224/384/512/768 screen; targeted confirmation |
| efficientnet_b0 | 2 | 0.52791 | 0.72962 | 0.0 | 0.08537 | 4013953.0 | 1135797.0 | 71.46289 | 0.00295 | 15.61279 | Grad-CAM compatible; fidelity untested | none locally; independent evaluation required | 224 only in this bounded study |
| resnet50 | 2 | 0.45179 | 0.74349 | 0.0 | 0.07317 | 23518277.0 | 14974981.0 | 344.43457 | 0.00301 | 90.02931 | Grad-CAM compatible; fidelity untested | none locally; independent evaluation required | 224 only in this bounded study |
| swin_t | 2 | 0.48513 | 0.743 | 0.0 | 0.06098 | 27523199.0 | 14189237.0 | 345.46387 | 0.00383 | 105.28209 | gradient maps / attention analysis; fidelity untested | none locally; independent evaluation required | 224 only in this bounded study |

## Complete grading packages: three folds × two seeds only

| stage | architecture | resolution | preprocessing | augmentation | objective | runs | folds | seeds | macro_f1_mean | macro_f1_std | qwk_mean | qwk_std | balanced_accuracy | minority_grade1_recall | undergrading_3_4_to_0_1 | nll | brier | ece | overfit_gap | training_seconds | parameters | approx_reference_GFLOPs | trainable_parameters |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| partial_fine_tuning | convnext_tiny | 512 | baseline | none | ce | 6 | 3 | 2 | 0.51806 | 0.02435 | 0.79235 | 0.05551 | 0.52644 | 0.11111 | 0.03313 | 1.61293 | 0.58348 | 0.22884 | 0.39278 | 44.25296 | 27823973 | 23.28033 | 15475973 |
| frozen | convnext_tiny | 512 | baseline | none | ce | 6 | 3 | 2 | 0.51118 | 0.01936 | 0.77129 | 0.04286 | 0.51641 | 0.08333 | 0.04553 | 1.42355 | 0.57655 | 0.2128 | 0.40327 | 0.40777 | 27823973 | 23.28033 | 3845 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | none | ce | 6 | 3 | 2 | 0.50906 | 0.03174 | 0.76769 | 0.04256 | 0.52088 | 0.13889 | 0.05346 | 1.54223 | 0.60082 | 0.2285 | 0.41636 | 24.99577 | 27823973 | 13.09518 | 15475973 |
| partial_fine_tuning | convnext_tiny | 224 | baseline | none | ce | 6 | 3 | 2 | 0.50658 | 0.04876 | 0.77544 | 0.04668 | 0.51724 | 0.16667 | 0.03323 | 1.56973 | 0.60602 | 0.23383 | 0.47845 | 11.06528 | 27823973 | 4.456 | 15475973 |
| frozen | convnext_tiny | 224 | baseline | none | ce | 6 | 3 | 2 | 0.50555 | 0.05047 | 0.77368 | 0.05025 | 0.51257 | 0.16667 | 0.03323 | 1.49329 | 0.61038 | 0.2376 | 0.45865 | 0.43868 | 27823973 | 4.456 | 3845 |
| frozen | convnext_tiny | 384 | baseline | none | ce | 6 | 3 | 2 | 0.49541 | 0.02704 | 0.75298 | 0.03876 | 0.50469 | 0.11111 | 0.05346 | 1.48919 | 0.61073 | 0.23106 | 0.37753 | 0.31542 | 27823973 | 13.09518 | 3845 |
| partial_fine_tuning | efficientnet_b0 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.49433 | 0.02939 | 0.73013 | 0.00735 | 0.49855 | 0.02778 | 0.06596 | 1.89546 | 0.65233 | 0.25134 | 0.45373 | 9.22812 | 4013953 | 0.386 | 1135797 |
| frozen | efficientnet_b0 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.48929 | 0.03435 | 0.71406 | 0.02525 | 0.49036 | 0.02778 | 0.11159 | 1.79127 | 0.64456 | 0.23915 | 0.4332 | 0.43285 | 4013953 | 0.386 | 6405 |
| frozen | swin_t | 224 | baseline | none | ce | 6 | 3 | 2 | 0.48527 | 0.00595 | 0.72037 | 0.04624 | 0.50961 | 0.22222 | 0.08283 | 1.55125 | 0.63761 | 0.23063 | 0.30726 | 0.49971 | 27523199 | 4.491 | 3845 |
| frozen | resnet50 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.45812 | 0.07101 | 0.68433 | 0.04666 | 0.47707 | 0.27778 | 0.06159 | 2.97089 | 0.79629 | 0.34765 | 0.40048 | 0.39432 | 23518277 | 4.089 | 10245 |

## Isolated resolution, preprocessing, augmentation and objective screens

| resolution | preprocessing | augmentation | objective | runs | macro_f1 | qwk | grade1_recall | undergrading | nll | training_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 224 | baseline | none | ce | 2 | 0.51937 | 0.81003 | 0.0 | 0.0122 | 1.39224 | 11.73531 |
| 384 | baseline | minimal | ce | 2 | 0.52239 | 0.79114 | 0.08333 | 0.08537 | 1.57199 | 24.87854 |
| 384 | baseline | moderate | ce | 2 | 0.51544 | 0.77894 | 0.0 | 0.06098 | 1.13158 | 26.57704 |
| 384 | baseline | none | ce | 2 | 0.53112 | 0.802 | 0.08333 | 0.08537 | 1.5791 | 25.37915 |
| 384 | baseline | none | focal | 2 | 0.51576 | 0.80115 | 0.0 | 0.06098 | 1.06508 | 24.90785 |
| 384 | baseline | none | ordinal | 2 | 0.52744 | 0.8001 | 0.08333 | 0.08537 | 1.52984 | 24.9097 |
| 384 | baseline | none | weighted_ce | 2 | 0.51745 | 0.76597 | 0.16667 | 0.07317 | 1.59266 | 24.80314 |
| 384 | crop | none | ce | 2 | 0.51335 | 0.75057 | 0.0 | 0.08537 | 1.30274 | 24.23931 |
| 512 | baseline | none | ce | 2 | 0.54065 | 0.84782 | 0.08333 | 0.02439 | 1.59904 | 46.55296 |
| 768 | baseline | none | ce | 2 | 0.5489 | 0.83669 | 0.08333 | 0.04878 | 1.11863 | 94.00066 |

These rows share fold0 and the two optimization seeds. Compare each transformation against the same-resolution baseline. A one-fold screen is exploratory. Matched baseline and selected-recipe confirmation on the other folds is kept separate; changes are never declared additive merely because each individually looks favorable. The 512 CE confirmation is a documented adaptive extension prompted by disagreement between macro-F1, QWK and MA preservation, not a retrospective claim of preregistration.

Selected-package pooled OOF metrics (each seed covers the same 404 development images once):

| seed | images | accuracy | balanced_accuracy | macro_f1 | weighted_f1 | qwk | mae_grade | distance_ge2_rate | high_grade_to_0_or_1_rate | grade0_to_3_or_4_count | nll | brier | ece_10_bins | minority_grade1_recall | roc_auc_ovr_macro |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17 | 404 | 0.60891 | 0.50676 | 0.50617 | 0.60993 | 0.7541 | 0.55941 | 0.14109 | 0.04959 | 3 | 1.53812 | 0.63478 | 0.24702 | 0.16667 | 0.82073 |
| 29 | 404 | 0.62376 | 0.51826 | 0.5179 | 0.62123 | 0.79172 | 0.51238 | 0.12376 | 0.01653 | 2 | 1.44833 | 0.58567 | 0.20916 | 0.16667 | 0.82542 |

## All grading packages, including exploratory partial screens

| stage | architecture | resolution | preprocessing | augmentation | objective | runs | folds | seeds | macro_f1_mean | macro_f1_std | qwk_mean | qwk_std | balanced_accuracy | minority_grade1_recall | undergrading_3_4_to_0_1 | nll | brier | ece | overfit_gap | training_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frozen | convnext_tiny | 224 | baseline | none | ce | 6 | 3 | 2 | 0.50555 | 0.05047 | 0.77368 | 0.05025 | 0.51257 | 0.16667 | 0.03323 | 1.49329 | 0.61038 | 0.2376 | 0.45865 | 0.43868 |
| frozen | convnext_tiny | 384 | baseline | none | ce | 6 | 3 | 2 | 0.49541 | 0.02704 | 0.75298 | 0.03876 | 0.50469 | 0.11111 | 0.05346 | 1.48919 | 0.61073 | 0.23106 | 0.37753 | 0.31542 |
| frozen | convnext_tiny | 384 | crop | none | ce | 2 | 1 | 2 | 0.51335 | 0.01627 | 0.75057 | 0.02814 | 0.51882 | 0.0 | 0.08537 | 1.30281 | 0.53828 | 0.17793 | 0.31941 | 0.25612 |
| frozen | convnext_tiny | 512 | baseline | none | ce | 6 | 3 | 2 | 0.51118 | 0.01936 | 0.77129 | 0.04286 | 0.51641 | 0.08333 | 0.04553 | 1.42355 | 0.57655 | 0.2128 | 0.40327 | 0.40777 |
| frozen | convnext_tiny | 768 | baseline | none | ce | 2 | 1 | 2 | 0.52461 | 0.00366 | 0.80645 | 0.01502 | 0.53241 | 0.0 | 0.04878 | 1.20431 | 0.53278 | 0.17845 | 0.4539 | 0.3749 |
| frozen | efficientnet_b0 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.48929 | 0.03435 | 0.71406 | 0.02525 | 0.49036 | 0.02778 | 0.11159 | 1.79127 | 0.64456 | 0.23915 | 0.4332 | 0.43285 |
| frozen | resnet50 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.45812 | 0.07101 | 0.68433 | 0.04666 | 0.47707 | 0.27778 | 0.06159 | 2.97089 | 0.79629 | 0.34765 | 0.40048 | 0.39432 |
| frozen | swin_t | 224 | baseline | none | ce | 6 | 3 | 2 | 0.48527 | 0.00595 | 0.72037 | 0.04624 | 0.50961 | 0.22222 | 0.08283 | 1.55125 | 0.63761 | 0.23063 | 0.30726 | 0.49971 |
| partial_fine_tuning | convnext_tiny | 224 | baseline | none | ce | 6 | 3 | 2 | 0.50658 | 0.04876 | 0.77544 | 0.04668 | 0.51724 | 0.16667 | 0.03323 | 1.56973 | 0.60602 | 0.23383 | 0.47845 | 11.06528 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | minimal | ce | 2 | 1 | 2 | 0.52239 | 0.01622 | 0.79114 | 0.00557 | 0.52798 | 0.08333 | 0.08537 | 1.57199 | 0.57798 | 0.23223 | 0.41278 | 24.87854 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | moderate | ce | 2 | 1 | 2 | 0.51544 | 0.00638 | 0.77894 | 0.01168 | 0.52493 | 0.0 | 0.06098 | 1.13158 | 0.53465 | 0.18637 | 0.3551 | 26.57704 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | none | ce | 6 | 3 | 2 | 0.50906 | 0.03174 | 0.76769 | 0.04256 | 0.52088 | 0.13889 | 0.05346 | 1.54223 | 0.60082 | 0.2285 | 0.41636 | 24.99577 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | none | focal | 2 | 1 | 2 | 0.51576 | 0.00684 | 0.80115 | 0.01972 | 0.52605 | 0.0 | 0.06098 | 1.06508 | 0.51418 | 0.15967 | 0.30466 | 24.90785 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | none | ordinal | 2 | 1 | 2 | 0.52744 | 0.02335 | 0.8001 | 0.01824 | 0.53201 | 0.08333 | 0.08537 | 1.52984 | 0.57063 | 0.2454 | 0.4418 | 24.9097 |
| partial_fine_tuning | convnext_tiny | 384 | baseline | none | weighted_ce | 2 | 1 | 2 | 0.51745 | 0.00454 | 0.76597 | 0.00291 | 0.52888 | 0.16667 | 0.07317 | 1.59266 | 0.56728 | 0.2039 | 0.38401 | 24.80314 |
| partial_fine_tuning | convnext_tiny | 384 | crop | none | ce | 2 | 1 | 2 | 0.51335 | 0.01627 | 0.75057 | 0.02814 | 0.51882 | 0.0 | 0.08537 | 1.30274 | 0.53823 | 0.17799 | 0.31941 | 24.23931 |
| partial_fine_tuning | convnext_tiny | 512 | baseline | none | ce | 6 | 3 | 2 | 0.51806 | 0.02435 | 0.79235 | 0.05551 | 0.52644 | 0.11111 | 0.03313 | 1.61293 | 0.58348 | 0.22884 | 0.39278 | 44.25296 |
| partial_fine_tuning | convnext_tiny | 768 | baseline | none | ce | 2 | 1 | 2 | 0.5489 | 0.00745 | 0.83669 | 0.02762 | 0.55355 | 0.08333 | 0.04878 | 1.11863 | 0.48251 | 0.17772 | 0.34313 | 94.00066 |
| partial_fine_tuning | efficientnet_b0 | 224 | baseline | none | ce | 6 | 3 | 2 | 0.49433 | 0.02939 | 0.73013 | 0.00735 | 0.49855 | 0.02778 | 0.06596 | 1.89546 | 0.65233 | 0.25134 | 0.45373 | 9.22812 |
| partial_fine_tuning | resnet50 | 224 | baseline | none | ce | 2 | 1 | 2 | 0.45179 | 0.01374 | 0.74349 | 0.02656 | 0.47752 | 0.0 | 0.07317 | 1.22428 | 0.5778 | 0.18517 | 0.34067 | 11.52511 |
| partial_fine_tuning | swin_t | 224 | baseline | none | ce | 2 | 1 | 2 | 0.48513 | 0.00256 | 0.743 | 0.02794 | 0.47441 | 0.0 | 0.06098 | 1.40356 | 0.60522 | 0.22629 | 0.43911 | 12.60047 |

The recommendation ranks mean macro-F1, then QWK. Within the declared 0.02 absolute macro-F1 and 0.02 QWK band around the best complete package, prefer lower reference compute and total parameters. For the same backbone/input, the final engineering tie-break prefers fewer trainable parameters. That tie-break was articulated after observing development CV and is transparently recorded in final_engineering_tiebreak_note.json; it is not retrospectively called preregistered. These are engineering tolerances, not significance tests, statistical equivalence, clinical noninferiority or a clinical utility score. No aggregate weighted score is used. Macro-F1, QWK, minority recall, severe undergrading bins, calibration and compute remain separate columns. All fitted head/partial-stage results and raw validation predictions are retained.

**Warm-start checkpoint finding:** 23 of 42 partial-tuning runs selected their pre-fine-tuning frozen-head checkpoint (best_epoch=-1). Fine-tuning was attempted, but was not automatically assumed beneficial. Overfit gap compares training versus validation macro-F1 at the selected checkpoint. Short six-epoch partial schedules, head-only warm-up, model-specific pretrained recipes and selected-checkpoint optimism limit architectural conclusions. A model eliminated in this screen is not proven inferior under all training budgets.

## Segmentation: native-image evaluation, no patch-level split

| architecture | mode | resolution | objective | runs | MA_dice | MA_dice_std | mean_dice | mean_dice_std | training_seconds | native_validation_seconds | peak_MiB | parameters | checkpoint_MiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DeepLabV3Plus | full | 512 | bce_dice | 2 | 0.0 | 0.0 | 0.11601 | 0.0385 | 18.29248 | 9.30781 | 638.96191 | 11647316 | 44.54217 |
| Segformer | full | 512 | bce_dice | 2 | 0.0 | 0.0 | 0.32374 | 0.04627 | 22.5941 | 11.39651 | 690.98193 | 3451748 | 13.24124 |
| Unet | full | 512 | bce | 2 | 0.0 | 0.0 | 0.05451 | 0.07531 | 21.33495 | 8.58045 | 680.38232 | 12461444 | 47.64241 |
| Unet | full | 512 | bce_dice | 2 | 0.0 | 0.0 | 0.1745 | 0.04678 | 22.27849 | 10.47134 | 690.78613 | 12461444 | 47.64331 |
| Unet | patch | 256 | bce | 2 | 0.0 | 0.0 | 0.02023 | 0.02861 | 22.41427 | 13.0255 | 361.14307 | 12461444 | 47.64259 |
| Unet | patch | 256 | bce_dice | 2 | 0.0 | 0.0 | 0.00779 | 0.01096 | 23.1411 | 12.86849 | 367.51758 | 12461444 | 47.64349 |
| Unet | patch | 512 | bce_dice | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 23.23671 | 14.00018 | 532.07227 | 12461444 | 47.64349 |
| UnetPlusPlus | full | 512 | bce_dice | 2 | 0.0 | 0.0 | 0.14062 | 0.03684 | 46.48007 | 9.71223 | 1015.27002 | 13965444 | 53.41772 |

**MA capability limitation:** No initial four-lesion package demonstrated nonzero MA Dice at the fixed threshold. There is no demonstrated MA-capable winner in that suite; its four-lesion mean leader is only a larger-lesion baseline. Zero Dice may reflect optimization, calibration/threshold, sparse supervision and resolution together; it cannot isolate resizing as the cause.

## Adaptive MA-only follow-up, analyzed separately

| mode | resolution | epochs | runs | MA_dice | MA_dice_std | recall | precision | component_recall | component_precision | training_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full | 512 | 12 | 2 | 0.28681 | 0.00278 | 0.27265 | 0.30284 | 0.25479 | 0.43814 | 47.57095 |
| patch | 256 | 12 | 2 | 0.16866 | 0.08273 | 0.72878 | 0.09825 | 0.7524 | 0.11068 | 54.1292 |

Adaptive MA-only follow-up leader: U-Net/ResNet18, full512, 12 epochs, 0.5 weighted BCE + 0.5 Tversky (FP=.3, FN=.7; training-only positive weight capped at 50). Mean native MA Dice=0.28681, recall=0.27265, precision=0.30284. This suite changes target/loss/schedule from the original four-lesion suite; input modes are compared within the matched follow-up, not as a pure resolution ablation across suites. It is a diagnostic experiment, not validated MA capability.

This four-fit extension (two input modes × two seeds) was motivated by empty MA predictions from the initial suite. Its source rationale is [Salehi et al., Tversky loss](https://arxiv.org/abs/1706.05721); MRI evidence does not establish retinal loss coefficients or clinical costs. The amendment is recorded before fitting. It uses one MA head, the same 40/10 image split, a longer common fixed budget, the same two seeds and held-out native images. Patch-positive sampling is MA-specific. BCE weights use training-native prevalence only, with an explicit engineering cap; coefficients are not tuned on the official test. MA-only Dice is never averaged as if it were a four-lesion score. PR/threshold analysis and independent validation remain needed before concluding capability.

**Numerical failure and recovery:** an exploratory FP16 MA patch run (seed29) developed NaN loss. Its thresholded empty-mask score is invalid and excluded, not treated as genuine zero capability. All four matched MA fits were rerun in FP32 with finite-loss/logit/gradient checks. Only that matched FP32 suite is ranked above. Original probe artifacts and the failure log are retained. Initial four-lesion checkpoints were also re-evaluated with finite-checked FP32 inference, preserving original AMP metrics and unchanged weights separately. This is a documented numerical correction, not test-driven tuning.

Segmentation used {'train': 40, 'validation': 10} within 50 eligible organizer training images; four potential grading-test correspondences were conservatively excluded before its split. All validation patches from one original image remain held out together. Pixel metrics are computed against native masks after reconstruction, with unavailable channels omitted. Threshold 0.5 was fixed. Component recall/precision use one-to-one eight-connected components matched at IoU≥0.1; these are geometric annotation regions, not adjudicated lesion diagnoses. Per-class results, including precision/recall/IoU and component detection, are saved separately.

U-Net/U-Net++/DeepLabV3+ share an ImageNet residual encoder; SegFormer uses MiT-B0. This compares packages, not decoders in isolation. All encoders are fine-tuned in segmentation; BatchNorm running statistics are frozen to accommodate full-image batch1 consistently. Decoder widths are bounded for the laptop. Full512 receives two views/image/epoch; patch256 receives eight and patch512 two. This matches nominal input-pixel and optimizer-update budgets, but full-image letterbox padding is excluded from supervised pixels, so supervised native-area coverage differs. Training patch sampling is half lesion-centered/type-uniform, half uniform; validation uses all tiles with no lesion selection. Both modes receive horizontal flips. Nonoverlapping tiling is computationally bounded but may introduce seams; overlapping/hybrid inference was not silently substituted.

BCE and BCE+Dice are the bounded initial loss comparison. Tversky is used only in the explicitly adaptive MA-only follow-up; focal segmentation loss is not an unrun winner. OD is excluded from lesion outputs so disc overlap cannot inflate lesion metrics. Empty patch regions from an available full mask are legitimate background; absent full-mask supervision is never background. Native RGBA alpha is excluded by the decoder. All runs use the same image-level validation split and two seeds; there is no segmentation K-fold claim. Every available MA mask is nonempty: background pixels within those images do not supply a verified cohort of MA-negative photographs. Image-level specificity on lesion-free screening photographs is unestablished. HE/SE metrics are conditional on annotation availability; unannotated image/type pairs cannot establish negatives.

## Calibration, errors and explanation compatibility

Accuracy, balanced accuracy, macro/weighted F1, QWK, per-class precision/recall/specificity, confusion matrices, OvR macro AUC, NLL, multiclass Brier and 10-bin ECE are recorded. Probabilities are raw; no calibration fit is evaluated on its own fit data. Error bins grade3/4→0/1 and grade0→3/4 are descriptive, not adopted referral thresholds. Galleries include common-screen errors for every grading family, high-confidence mistakes, low-confidence cases and minority-grade mistakes. Brightness/contrast/black fraction/blur-proxy quartiles are descriptive associations, not causal explanations or gradability labels. Lesion-size correlation is not supportable for all 404 images: only three exact cross-task correspondences exist; candidates were not assigned lesion labels for this analysis.

CNN gradients and hierarchical attention support explanation tooling, but no explanation-fidelity or clinician-benefit evaluation was performed. No model can be awarded external-validation performance from an architecture alone. Approximate cross-task identities and patient identities remain unresolved, even though protected test paths were not accessed.

## Compute, failure log and limitations

Sum of recorded grading/head/segmentation fitting durations: 1855.7 seconds (excludes weight downloads, raw decoding/caching, some initialization and analysis). Runtime is measured on this machine and is not portable. Peak allocated MiB measures PyTorch tensors, not total display/system VRAM. Cached-image grading latency includes normalization/batching and probability output; native segmentation validation time also includes reconstruction/component analysis, and is not pure GPU latency. Approximate torchvision 224 reference GFLOPs are not a measured retinal-task FLOP trace; resolution-square scaling is a CNN approximation and not exact Swin cost.

Recorded failed runs:

```
{"operation": "MA numerical stability audit", "tag": "ma_Unet_patch256_weighted_bce_tversky_e12_s29", "status": "FAILED_EXCLUDED", "error": "Nonfinite training loss; original thresholded zero scores are INVALID and excluded, not genuine zero capability.", "recovery": "all four matched MA fits rerun in FP32 with finite checks"}

```

No low sample-size confidence interval can remove patient dependence or repeated model-selection bias. Image-bootstrap intervals are descriptive for the selected development pipeline, not selection-corrected patient-level inference. All confidence/error results need independent verification. The official test remains unscored.
