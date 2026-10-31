# Claims Ledger

Every number or assertion that may appear on a slide, in the demo or in an answer to a judge must have a row here.
Types: **E** our experiment · **P** published (verified) · **P?** published (not re-verified) · **G** clinical guideline · **H** hypothesis.

| ID | Claim | Type | Source | Evidence | Limitation | Safe wording |
|---|---|---|---|---|---|---|
| C01 | IDRiD grading set has 516 files but 510 distinct photographs | E | `docs/dataset_audit/IDRiD_DATASET_AUDIT.md` | SHA-256 of decoded pixels | Exact duplicates only | "Our audit found 6 exact-duplicate groups among 516 grading files." |
| C02 | 4 duplicate groups carry conflicting DR/DME labels, incl. a cross-split pair graded 0 (train) and 3 (test) | E | `IDRiD_LIMITATIONS.md` | Hash table | We did not determine which label is correct | "Identical images carry different grades; we quarantined them rather than relabel." |
| C03 | Clean protocol: 404 train / 102 test / 10 excluded; 26 integrity checks pass | E | `IDRiD_EXPERIMENT_POLICY.md` | Reproducible manifests | Patient independence unknown | "Image-level clean split; patient independence cannot be verified." |
| C04 | Resizing to width 224 removes 35.5% of MA annotation components (1.3% at 512, 0.06% at 1024) | E | `IDRiD_RESOLUTION_FINDINGS.md` | Nearest-neighbour mask sampling | Geometric sampling, not model performance | "Downsampling to 224 px erases about a third of annotated microaneurysm regions." |
| C05 | Frozen ConvNeXt-T @224: macro-F1 0.506, QWK 0.774 (3-fold × 2-seed OOF) | E | `outputs/metrics/model_selection/grading_scorecard.csv` | CV on clean train | 6-epoch-class budget; not a test result | "Development baseline (cross-validation), not a test score." |
| C06 | Grade-1 recall 16.7% (3/18); Wilson 95% CI ≈ 5.8–39% | E | `selected_grading_per_class_seed17.csv` | 18 support | n too small to evaluate fixes | "Mild NPDR is our weakest class, and IDRiD has too few examples to measure improvement reliably." |
| C07 | OOF ECE 0.21–0.25 | E | `selected_grading_OOF_metrics.csv` | 10-bin ECE | Uncalibrated baseline | "Raw softmax confidence is miscalibrated; we do not display it uncorrected." |
| C08 | Fine-tuning / larger input did not help *in a 6-epoch screen* | E | configs `max_epochs: 6` | Scorecard | Confounded with under-training | Never say "fine-tuning doesn't help". Say "did not help within a short screening budget". |
| C09 | SegFormer-B0 @512: mean Dice 0.324 across lesions, MA Dice 0 at threshold 0.5 | E | `segmentation_scorecard.csv` | 40 train / 10 val images, 6 epochs | Tiny, under-trained, fixed threshold | "Initial short screen; MA undetected at a fixed threshold." |
| C10 | MA-only U-Net full512: Dice 0.287 vs native-patch256 0.169; patch recall 0.73 vs 0.27, precision 0.10 vs 0.30 | E | `MA_specialist_scorecard.csv` | 10 val images, 2 seeds | Patch sampling was 50% lesion-centred (prior shift confound) | "Native patches raised recall but produced many false positives in our setup." |
| C11 | RETFound: ViT-L MAE, 904,170 CFP (815,468 MEH-MIDAS + 88,702 Kaggle EyePACS); ~1.6M images incl. OCT | P | Zhou et al., Nature 2023, doi:10.1038/s41586-023-06555-x | Methods | — | As stated, cite paper |
| C12 | RETFound IDRiD 5-class AUROC 0.822 (paper's split) | P | Same | Results | Different split from ours | "Paper-reported", never compared numerically to ours as head-to-head |
| C13 | MMRDR: 11,118 CFP / 10,404 UWF / 2,938 OCT; CC BY 4.0; 18.6 GB | P | Tang et al., Sci Data 2026; figshare v2 | Paper + figshare API | — | Cite |
| C14 | MMRDR-CFP comes from OIA-DDR; split at image level (no patient IDs) | P | Same | Paper text | — | "MMRDR-CFP does not support patient-level generalisation claims." |
| C15 | MMRDR-CFP lesion labels are image-level 7-way presence (MA, EX, IRH, VB/IRMA, NV, VH, RD), not masks | P | Same | Paper text | Verify CSV in S1 | "Image-level lesion presence labels" |
| C16 | On MMRDR-CFP, fine-tuned RETFound ≈ ResNet-50 (acc 0.822 vs 0.823; F1 0.714 vs 0.702) | P | Same | Baseline table | Authors' setup | "On large data, the paper found little gap between RETFound and ResNet-50." |
| C17 | Inter-grader κ for DR grading reported 0.40–0.65 | P | Krause et al. 2018 (arXiv:1710.01711) | Intro | Literature summary | "Even experts disagree substantially on DR grade." |
| C18 | RETFound-DINOv2 > generalist DINOv2/v3 on ocular tasks | P (preprint) | arXiv:2509.03421 | Abstract | Not peer-reviewed | "A 2025 preprint reports…" |
| H01 | RETFound advantage, if any, is larger at IDRiD scale than at MMRDR scale | H | C12, C16 | — | Untested | Don't present as a finding |
| H02 | Grade-1 failure is partly a resolution/MA-visibility effect | H | C04, C06 | — | Untested; n too small on IDRiD | Hypothesis only |
| H03 | Patch FP explosion is driven by the training-sampling prior, not only missing context | H | C10 config | — | Untested | Hypothesis only |
| H04 | VB/IRMA/NV presence supervision improves severe/PDR grading | H | C15 | — | Untested (RQ5) | Hypothesis only |
