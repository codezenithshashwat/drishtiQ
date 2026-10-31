# Model-selection study execution summary

The bounded development study is complete. The 102-image clean grading test and official segmentation test were not evaluated. Raw data remained read-only, and every stage's raw path/size/modification-time comparison passed. Patient independence remains unknown.

## Experiments performed

- Reviewed 21 primary-source papers/records, distinguishing reported results, preprints, inaccessible methods and local experiments. The initial 20-source review preceded initial fitting; Tversky was added before the adaptive MA follow-up.
- Compared pretrained ResNet50, EfficientNet-B0, ConvNeXt-Tiny and Swin-Tiny. All received frozen-feature three-fold/two-seed evaluation and a common partial-tuning screen. Two finalists received expanded cross-validation.
- Screened 224/384/512/768 inputs on the shortlisted backbone; compared cropping, augmentation, weighted CE, focal and ordinal-aware objectives. Confirmed selected-resolution and 512 baselines on the other folds.
- Compared U-Net, U-Net++, DeepLabV3+ and SegFormer; investigated full-image versus native 256/512 patches, unavailable-mask gating, BCE and BCE+Dice.
- Investigated initial MA failures with a separate matched MA-only U-Net study: full512 versus native256, two seeds, weighted BCE plus Tversky, twelve epochs. An unstable AMP probe was excluded; the entire matched MA suite was rerun in FP32.

## Recommendations supported by this study

**Grading research baseline:** frozen ImageNet ConvNeXt-Tiny features plus a linear five-grade head, 224-width aspect-preserved input, standard normalization and CE. Mean fold/seed macro-F1 0.506; QWK 0.774. Larger inputs and partial fine-tuning did not justify their added cost under the declared development tolerance. Grade-1 recall was only 16.7%, so this is not a ready final classifier.

**Initial four-lesion baseline:** SegFormer-B0/full512/BCE+Dice had the highest mean Dice, 0.324, but no MA detection at the fixed threshold. It must not be described as solving MA segmentation.

**MA-only follow-up:** full512 U-Net achieved mean MA Dice 0.287, versus 0.169 for native256 patches. Patches increased pixel recall (0.729 versus 0.273), while reducing precision (0.098 versus 0.303). Preserving pixels alone did not produce the best precision/Dice trade-off. These results are limited to ten internal validation images and two seeds; no final clinical MA model is established.

No multi-task/fusion model, clinical referral policy, final all-development-data fit or external validation was performed.

## Verification and next reading

320 checks and eight protocol tests passed. Forty figures were decoded. One historical numerical failure is retained and excluded; the four matched FP32 MA fits and sixteen original-suite checkpoint inference rechecks passed. The final results use standardized numerical probability scoring without changing hard predictions or selection metrics.

Read DR_ARCHITECTURE_RECOMMENDATION.md, DR_MODEL_SELECTION_SCORECARD.md, DR_MODEL_LITERATURE_REVIEW.md and STUDY_PROTOCOL_AND_REPRODUCIBILITY.md. Detailed checks are in outputs/metrics/model_selection/study_validation_checks.csv; experiment_registry.csv distinguishes primary comparisons from unranked/invalid probes. Source, configurations, predictions, histories, weights and dependency versions are preserved for protocol replication.
