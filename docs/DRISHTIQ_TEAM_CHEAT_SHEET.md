# DrishtiQ — Team Cheat Sheet

Two-page summary of the [team handbook](DRISHTIQ_TEAM_TECHNICAL_HANDBOOK.md). Every number below is traced there to its source file.
Labels: **[IMPL]** implemented · **[EXP]** experiment · **[PROP]** proposed · **[REJ]** rejected.

**PRODUCT.** AI-assisted diabetic-retinopathy screening and clinical decision support. In: one fundus photo per eye + patient ID +
two optional intake answers. Out: quality check / retake, stage 0–4, lesion overlays, Grad-CAM, calibrated chance of referable DR,
confidence, an urgency-ordered worklist, doctor report, patient summary (EN/HI). The ophthalmologist decides. Research prototype, not a
medical device. Frozen as `rc-1` (commit `564c7b7`); the DrishtiQ interface is on branch `ui-v3`.

**PROBLEM.** Not "classify images": the scarce resource is **specialist attention**. Bad photos found after the patient leaves, and
unsorted results, waste it — especially in rural screening.

**PIPELINE.** Photo → EXIF/RGB → heuristic quality check (retake) → ConvNeXt-T grader (one severity score → stage) → Grad-CAM. In
parallel: SegFormer-B0 (HE/EX/SE) + U-Net/ResNet18 (MA) → pp_v2 thresholds → overlays and counts. Optic disc + fovea heuristics →
macular "swelling risk" proxy. Then Platt P(referable) + isotonic confidence + routing rules → worklist → clinician review → report.
**Lesion masks do not feed the grader.**

**ACTIVE GRADER [IMPL].** timm `convnext_tiny.fb_in1k`, ImageNet-pretrained, **fully fine-tuned**, regression head 768 → 1.
**27,820,897 parameters**; checkpoint 111,363,403 B (≈ 106 MiB); input 384 × 384. Cut points **0.527 / 1.408 / 2.636 / 3.464**.
API "probabilities" are one-hot (regression); the real probability is the calibrated P(referable).

**TRAINING DATA.** 14,063 images = IDRiD 303 + APTOS 2,929 + MMRDR 10,831. Inner split 11,250 train / **2,813 hold-out** (stopping, cut
points, calibration, routing thresholds). Development validation: IDRiD-val 101, APTOS-val 518. Locked: IDRiD clean test 102, DeepDRiD 1,988.

**PREPROCESSING.** EXIF-aware load → RGB → FOV crop (pixels > 15) → centred square pad → bilinear 384 → ÷255 → ImageNet mean/std.
Identical in training and runtime. Training-only augmentation: flips, rotation ±180°, scale 0.95–1.05, brightness/contrast ±10%.

**TRAINING PARAMETERS.** Smooth-L1 · AdamW · lr 2e-4 with layer multipliers (0.25 → 0.8, head ×5) · weight decay 0.05 · micro-batch 16 ×
accumulation 2 = **effective 32** · gradient clip 2 · AMP + gradient checkpointing · 1 warm-up epoch + cosine · max 15 epochs ·
patience 4 · seed 17 · dataset-balanced sampling with 1/√ class weights · best = **15th (last) epoch** · ≈ 92 min on an RTX 3050 (4 GB).

**TOP METRICS**

| | QWK | Referable sens / spec | AUROC | n |
|---|---|---|---|---|
| IDRiD-val (dev) | 0.893 | 93.7% / 100% | 0.992 | 101 |
| APTOS-val (dev) | 0.918 | 95.0% / 90.5% | 0.975 | 518 |
| **IDRiD clean test (locked)** | **0.816** | **90.5% / 89.7%** | **0.943** | 102 |
| **DeepDRiD (locked, external)** | **0.780** | **93.0% / 84.2%** | **0.946** | 1,977 |

**SEGMENTATION MODELS [IMPL].** MA: U-Net/ResNet18, 12,461,009 params, 12 epochs. HE/EX/SE: SegFormer-B0, 3,451,748 params, 6 epochs.
Both trained on **40** IDRiD images. IDRiD-val Dice MA 0.275 · HE 0.422 · EX 0.559 · SE 0.447 (10/10/10/5 images). DDR-test AUPR MA 0.053.

**BIGGEST STRENGTH.** Integrity and honesty: clean data, rules written before results, a frozen system tested once, negative results reported.

**BIGGEST WEAKNESS.** Grade 1 (IDRiD-val 1/5, APTOS-val 19/50, locked test 0/5) and Grade 4 (4/12, 22/39); MA localisation; quality check
agrees only 53.6% with DeepDRiD quality labels.

**LOCKED TEST RESULT.** IDRiD test: grading holds (QWK 0.816), but **autonomous routine routing failed: 5 of 63 referable eyes routed to
routine (7.9%, upper bound 17.6%) vs a 2.5% target and 4.5% tolerance**, including a grade-3 eye called stage 0 at confidence 0.956.
DeepDRiD: 0/248 referable patients routed to routine, but only 7% routed there.

**WHY CONVNEXT.** Best of 4 backbones in the prior study (frozen 0.506 / 0.774), better than EfficientNet-B3 in every matched fine-tune,
passed the pre-registered swap rule (ΔQWK +0.098 / +0.198), fits a 4 GB GPU, ≈ 1 s/image. Not "clinically optimal".

**WHY NOT RETFOUND.** Frozen-probe gains were real but not significant (ΔQWK +0.030 [−0.065, 0.129] IDRiD; +0.020 [−0.018, 0.061] APTOS),
so the pre-registered rule failed; a 303 M-parameter ViT-L cannot be fine-tuned on 4 GB. Not proven worse — not proven better.

**WHY QWK.** Stages are ordered; QWK penalises 3 → 0 far more than 3 → 2 (squared distance).

**WHY NOT ACCURACY ONLY.** Classes are imbalanced (most eyes are stage 0); accuracy hides weak rare classes and ignores error size.

**WHY 384 IS A PROBLEM FOR MA.** One grader pixel ≈ 8.9 × 8.9 native pixels; on IDRiD_21 the median microaneurysm becomes 2.85 pixels and
7 of 80 drop below one pixel; across IDRiD, 5.6% of MA components vanish at 384 (35.5% at 224). Geometric evidence, not proof of a specific error.

**WHAT GRAD-CAM MEANS.** Where the grading model's evidence came from (attribution). Not a lesion detector, not proof of disease.

**WHAT SEGMENTATION MEANS.** Separate models predicting which pixels are MA/HE/EX/SE. Counts = connected regions, not confirmed lesions.

**WHAT 99% MEANS.** A calibrated estimate on held-out development data. Not clinical certainty; confident errors happened on locked data.

**WHAT WE CANNOT CLAIM.** Diagnosis · safe autonomous routing · PDR detection · DME diagnosis · verified lesion counts · validation for
rural India · DDR as an independent grading test · Messidor-2 results · that a clinician's correction updates the report's routing.

**FUTURE ARCHITECTURE [PROP].** Modality check → task-aware gradability → OOD check → anatomy → global + selected high-resolution local
analysis → grading + advanced-sign analysis → consistency checks → calibrated reliability → abstain/retake/review → bilateral
assessment → prioritisation → clinician sign-off → report. Each part to be validated by its own pre-registered test.

**ONE-SENTENCE JUDGE ANSWER.**
> "DrishtiQ is an AI-assisted DR screening tool that checks photo quality, suggests a severity stage with calibrated confidence and lesion
> evidence, and orders the specialist's worklist; we froze it and tested it once on locked data, and our own results show it supports
> prioritisation with clinician review — not autonomous decisions."
