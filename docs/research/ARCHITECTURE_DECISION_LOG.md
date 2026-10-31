# Architecture Decision Log

Status values: **Proposed** (awaiting team approval) · **Accepted** · **Superseded** · **Rejected**.
A decision changes only through a new entry. Never edit history.

---

## ADR-001 — IDRiD clean protocol as primary internal benchmark
- **Status:** Accepted (prior work)
- **Decision:** 404/102 clean split; quarantine 8 conflicting-duplicate images; drop 2 redundant duplicates; the official split is secondary only.
- **Alternatives:** official split; relabel conflicts; move images across splits.
- **Evidence:** C01–C03.
- **Trade-off:** 10 fewer images; non-standard benchmark, so not directly comparable to published IDRiD numbers.
- **Revisit if:** organisers publish corrected labels or patient IDs.

## ADR-002 — Prior model-selection conclusions downgraded to "screening evidence"
- **Status:** Proposed
- **Decision:** treat "fine-tuning / larger input / patches don't help" as unresolved, because the screens used 6 epochs and segmentation used 40 training / 10 validation images.
- **Evidence:** configs `max_epochs: 6`, `epochs: 6`, `training_images: 40`.
- **Trade-off:** costs one re-baselining stage (S2).
- **Revisit if:** S2 convergence-checked runs reproduce the same ordering.

## ADR-003 — RETFound is a candidate, not a decision
- **Status:** Proposed
- **Decision:** run a controlled comparison: ConvNeXt (ImageNet) vs RETFound-MAE-CFP (LP + FT); optionally RETFound-DINOv2 and RETFound-Green. Use pretrained-only CFP weights. Never use OCT weights or the released fine-tuned checkpoints.
- **Decision rule:** adopt RETFound only if IDRiD paired-bootstrap QWK gain CI > 0 and severe under-grading is not worse.
- **Evidence:** C11, C12, C16, C18; hardware constraint (4 GB VRAM).
- **Trade-off:** ViT-L needs cloud GPU for FT, and CPU inference is slow.
- **Revisit if:** the decision rule fails, or deployment latency is unacceptable.

## ADR-004 — Acquire MMRDR-CFP (extract only CFP from the full archive)
- **Status:** Proposed
- **Decision:** download all 9 parts (18.6 GB; required by multi-volume zip) and extract `MMRDR-CFP/` only. Role: supervised adaptation + internal validation/test. Never external.
- **Alternatives:** DDR directly (no 7-lesion labels, includes ungradable class); APTOS (smaller, noisy); EyePACS (in RETFound pretraining, very noisy).
- **Evidence:** C13–C16; mild-NPDR n = 1,302 vs IDRiD's 18.
- **Trade-off:** image-level splits; same lineage as DDR, so DDR-derived sets are barred as external.
- **Revisit if:** the S1 audit finds heavy cross-split duplication or a schema that differs from the paper.

## ADR-005 — Messidor-2 as the primary locked external test
- **Status:** Proposed
- **Decision:** Messidor-2 with a single adjudicated label source (Krause 2018 grades), evaluated once after lock. APTOS-2019 is the secondary external test if audited.
- **Alternatives:** DDR (lineage conflict); EyePACS (in RETFound pretraining); none.
- **Evidence:** C11, C14, lineage analysis in BLUEPRINT_V2 §7.
- **Trade-off:** few PDR cases; licence acceptance needed.
- **Revisit if:** licence unobtainable.

## ADR-006 — Separate grading and segmentation models
- **Status:** Proposed
- **Decision:** no multi-task fusion by default. The lesion-presence auxiliary head is tested only as an ablation (RQ5).
- **Evidence:** only 3 exact IDRiD cross-task links (W9); no controlled benefit shown.
- **Revisit if:** RQ5 shows a paired improvement.

## ADR-007 — Clinical endpoint reporting
- **Status:** Proposed
- **Decision:** in addition to 5-class metrics, report referable DR (grade ≥2) sensitivity/specificity, vision-threatening (≥3) sensitivity, and severe under-grading rate.
- **Evidence:** screening programme norms (Gulshan 2016, Abràmoff 2018 [P?]).
- **Revisit if:** never; these are additions.

## ADR-008 — Serving architecture
- **Status:** Proposed
- **Decision:** a single FastAPI process with in-process PyTorch models loaded at startup; React+Vite frontend; Docker; offline.
- **Alternatives:** microservices, Triton, cloud API.
- **Reason:** hackathon scope; rural/offline story; fewer failure points.
- **Revisit if:** concurrent load requirements appear.

## ADR-009 — Prototype-first, in parallel with the data audit (team decision, 2026-10-28)
- **Status:** Accepted
- **Decision:**
  - Build a minimal end-to-end prototype now: grader, segmentation, Grad-CAM, FastAPI and UI.
  - The full dataset-role contract no longer blocks modelling.
  - APTOS-2019 becomes grading **training** data (no longer a secondary external test).
  - DDR pixel masks become segmentation training data. All DDR-derived data stays training-side only.
  - Messidor-2 remains the only locked external test.
- **Supersedes:** the S1→S2 gate in ADR-004/005 and BLUEPRINT_V2 §12.
- **Guard kept:** before any training on APTOS or DDR, hash-check them against the IDRiD clean test and Messidor-2. This is cheap and protects the locked test sets.
- **Prototype v0:**
  - frozen ConvNeXt-T @224 with 6 dev heads (3 folds × 2 seeds), averaged
  - SegFormer-B0 for HE/EX/SE
  - MA-only U-Net
  - fixed 0.5 thresholds, uncalibrated

  These are IDRiD development checkpoints, swapped out once the APTOS+IDRiD grader exists.
- **Revisit if:** the deadline allows the audit-first order again.

## ADR-010 — Baseline row is the dev-train-only frozen head, not app v0 (2026-10-28)
- **Status:** Accepted
- **Decision:** The comparison baseline is frozen ConvNeXt-T @224 with a 3-seed linear-head ensemble trained on `configs/splits/idrid_grading_devtrain.csv` only.
- **Evidence:** App v0's 6 cross-validation heads saw every validation image during training. On the frozen val split they score QWK 0.98, an in-sample number; the clean recipe scores QWK 0.79.
- **Note:** The evaluation harness avoids pandas, because Windows Smart App Control blocks pandas 3.1.0's compiled extensions on this machine.

## ADR-011 — Lesion post-processing pp_v2 swapped into the app (2026-10-28)
- **Status:** Accepted
- **Decision:** The app applies `configs/postprocess/pp_v2.json` to the v0 lesion maps:
  - MA: threshold 0.7, minimum area 40 px, optic disc masked
  - HE: threshold 0.5, minimum area 20 px
  - EX: threshold 0.7, optic disc masked
  - SE: threshold 0.4, minimum area 200 px
  - areas are measured at 4288 px width
- **How it was selected:** maximum pooled Dice on 5-fold out-of-fold maps of the 50 dev segmentation images, under the constraint "no more false-positive regions on grade-0 images than without post-processing". False positives were measured with the fold-4 model on the 100 grade-0 dev-train grading images.
- **Rejected alternative:** `pp_v1` was the Dice-only choice. It raised HE false positives on grade-0 images.
- **Evidence (registry):**
  - Out-of-fold Dice is up for every lesion.
  - Validation false-positive regions per grade-0 image: MA 5.6→2.8, EX 11.2→8.1, HE 2.3→2.2, SE 2.6→2.5.
  - Validation Dice is within ±0.01 of before; AUPR is unchanged.
- **Caveat:** The 10-image validation split is fold 4 of the cross-validation, so it is not independent of the selection. The optic-disc locator is a brightness heuristic: it found the centre within one disc radius in 49/50 dev images.

## ADR-012 — RETFound linear probe does not replace ConvNeXt as the frozen backbone (2026-10-28)
- **Status:** Accepted (pre-registered rule applied)
- **Protocol:**
  - identical field-of-view crop at 224 and ImageNet normalisation for both backbones
  - same linear-head recipe with 3 seeds
  - inner 20% hold-out stratified by dataset x grade
  - paired bootstrap (2,000 resamples) on IDRiD-val (101) and APTOS-val (518)
- **Rule:** adopt RETFound only if the ΔQWK CI is above zero on at least one validation set, it is not worse on the other, and severe under-grading does not increase.
- **Result when trained on IDRiD dev-train + APTOS-train:**
  - ΔQWK (RETFound − ConvNeXt): +0.030 [−0.065, 0.129] on IDRiD; +0.020 [−0.018, 0.061] on APTOS. The rule fails.
  - ΔMacro-F1 on APTOS is +0.086 [0.016, 0.155] (not the pre-registered metric).
- **Result when trained on IDRiD only:** RETFound is much worse on APTOS (QWK 0.19 vs 0.68).
- **Consequence:** RETFound full fine-tuning on Kaggle is not started. ConvNeXt remains the backbone for A2.

- **Addendum (sanity check):** The official RETFound pooling (`models_vit.py`) is: mean of the raw patch tokens, then a fresh `fc_norm` LayerNorm; the pretrained `norm` is deleted. The A1 probe instead applied the pretrained `norm` before pooling. Input normalisation (ImageNet mean/std) matched.
  - The IDRiD-only probe was re-run with official pooling (backbone `retfound_cfp_officialpool`): IDRiD-val QWK 0.718 (was 0.722), APTOS-val 0.150 (was 0.187).
  - No material change, so the decision stands.
  - The official eval crop (resize 256, centre-crop 224) was deliberately not used: both backbones share the FOV crop at 224.

## ADR-013 — Pre-registered app-swap rule for graders (2026-10-28, before any A2 result)
- **Status:** Accepted
- **Rule:** A candidate grader replaces the app grader only if, by paired bootstrap (2,000 resamples, `python -m eval.compare`) against the comparator, all of these hold:
  1. The ΔQWK CI is above 0 on at least one of IDRiD-val and APTOS-val.
  2. The ΔQWK CI lower bound is above −0.05 on the other.
  3. Severe under-grading (true 3–4 → 0–1) does not significantly increase on either; the Δ CI lower bound must not be above 0.
- **Comparator:** The deployed app heads (v0) were trained on folds that include every IDRiD-val image (in-sample QWK 0.98), so they cannot serve as a comparator. The comparator is their clean replica: the same recipe (frozen ConvNeXt-T, letterbox 224, linear heads) trained on dev-train only (`frozen_convnext224_devtrain_v1`; QWK 0.795 / 0.720).
- **Preprocessing:** All new graders use the FOV crop (`plain` / `fovcrop`). The registry description states the preprocessing.
- **Model selection:** Only on inner hold-outs. A candidate is fixed before it is compared.

## ADR-014 — A3 segmentation data policy (2026-10-29, before A3 training)
- **Status:** Accepted
- **Training pool:** DDR lesion-segmentation train + valid (527 after near-copy removal) plus the IDRiD dev segmentation images in the existing 5-fold CV.
- **DDR official test (225):** never trained on. It is a second segmentation validation set.
- **Reported on:** IDRiD 5-fold CV out-of-fold maps (50), IDRiD 10-image val, and DDR-test. Metrics are AUPR (challenge convention), Dice and grade-0 false-positive regions per lesion.
- **Overlap note:** DDR-test images overlap MMRDR-CFP, which is grader training data (647/757 DDR lesion images are near-copies). That is acceptable for segmentation evaluation. DDR-test images are **excluded from any A4 lesion-to-grade fusion evaluation**, because the grader has seen them.
- **Recipe:**
  - common scale: FOV resized to 1,536 px
  - patches sampled uniformly over the FOV (natural lesion frequency, not 50% lesion-centred)
  - per-lesion supervision gating (missing IDRiD masks are not negatives; empty DDR masks are)
  - Gaussian-blended sliding-window inference at full image
  - post-processing re-selected with the grade-0 false-positive constraint (as ADR-011)
- **Swap rule:** A3 swaps into the app only if it beats v0.1 (pp_v2) on the registry.
- **After A3:** the macular-edema rule is refitted on dev-train only.

## ADR-015 — A2 candidate fixed by inner hold-out (2026-10-29, before any validation evaluation)
- **Status:** Accepted
- **Screen (seed 17, 15 epochs, dataset-balanced sampling, sqrt class weights):** best inner QWK — regression 384 px 0.929 (epoch 14), regression 512 px 0.928 (epoch 13), cross-entropy 384 px 0.918 (epoch 13).
- **Decision:** `convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17` is the A2 candidate. 512 px gives no inner gain at 1.8x the training time; CE is lower.
- **Next:** only this candidate is compared under ADR-013. The other two runs are not evaluated on IDRiD-val or APTOS-val.

## ADR-016 — Pre-registered A3 segmentation swap rule (2026-10-29, before A3 training)
- **Status:** Accepted. Replaces the looser "beats v0.1" line in ADR-014.
- **Per lesion (MA, HE, EX, SE),** the new model replaces v0.1 (pp_v2) only if all hold:
  1. AUPR improves on IDRiD 5-fold CV out-of-fold maps.
  2. AUPR improves on DDR-test (225).
  3. AUPR on IDRiD-val (10 images) does not drop by more than 0.05.
  4. Mean grade-0 false-positive regions (IDRiD grading-val, grade 0, as counted by the app) do not increase.
- **Post-processing** for the new model is re-selected on training-side data only (IDRiD CV out-of-fold maps), with the existing grade-0 false-positive constraint (ADR-011).
- **Application:** mechanical, per lesion, by the GPU queue (`tools/rules.py`). The app can mix lesions from v0.1 and A3. The swap is a config change and reversible.

## ADR-017 — Pre-registered A2 ensemble rule (2026-10-29, before seeds 23 and 41 are trained)
- **Status:** Accepted
- **Candidate:** an equal-weight ensemble of `convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1` seeds 17, 23 and 41 (same recipe). The regression scores are averaged and compared with the mean of the per-seed inner-hold-out thresholds, as `FinetunedGrader` does (corrected 2026-10-29, before training).
- **Comparator:** the single seed-17 model.
- **Rule:** the same three conditions as ADR-013, by paired bootstrap on IDRiD-val and APTOS-val:
  1. The ΔQWK CI is above 0 on at least one set.
  2. The lower bound is above −0.05 on the other.
  3. Severe under-grading does not significantly increase.
- **Inference time** (s/image, venv GPU) is reported for both and is not part of the rule.

## ADR-018 — Pre-registered pseudo-labelling experiment (2026-10-29; record only, no automatic swap)
- **Pool:** APTOS `test_images` (unlabelled). A structure-hash leak check runs first against IDRiD-val, APTOS-val and the IDRiD locked test. Any image at distance ≤42 from any of those is dropped.
- **Teacher:** the app grader after the ensemble decision.
- **Confidence threshold:** keep an image if the teacher's regression score lies within d of the nearest integer grade. d is the largest value in {0.10, 0.20, 0.30, 0.40} for which the teacher's accuracy on retained inner hold-out images is ≥0.90. It is fixed on the inner hold-out only.
- **Student:** the reg384 recipe, seed 17, trained on the mixed pool plus the pseudo-labels.
- **Evaluation:** the ADR-013 comparison against the teacher's single model. The result is recorded only; the user decides.

## ADR-019 — Pre-registered B5 calibration and abstention (2026-10-29, before any calibration result)
- **Status:** Accepted
- **Fit set:** the fine-tuner's inner hold-out (20% of the mixed pool, stratified dataset x grade, never trained on), scored by the app grader. IDRiD-val and APTOS-val are used for reporting only.
- **Outputs** for a regression grader with score s and thresholds t:
  1. P(referable): Platt scaling (logistic regression on s), predicting grade ≥2.
  2. Stage confidence: isotonic regression of 1[predicted stage = true stage] on the margin m = min_k |s − t_k|.
- **Abstention:** the AI defers ("refer for human grading") when stage confidence < τ. τ is the smallest value in {0.50, 0.55, …, 0.95} for which accuracy on retained inner-hold-out images is ≥ 0.85. If none qualifies, τ = 0.95.
- **Reported on IDRiD-val and APTOS-val:** ECE (10 equal-width bins) for both outputs, before calibration (raw margin rescaled to [0, 1]; P(referable) = 1[pred ≥ 2]) and after. Also coverage, accuracy on retained and on deferred images, and severe under-grading on retained images.
- **Re-run:** whenever the app grader changes. The file is keyed by the grader spec, and the app shows calibration only when the keys match.

## ADR-020 — Pre-registered B6 triage metric (2026-10-29)
- **Worklist order:**
  1. Images the AI defers on (ADR-019) or that fail the quality check.
  2. Then by calibrated P(referable), descending.
- **Metrics per validation set (IDRiD-val, APTOS-val):**
  - AUROC of P(referable) for referable DR (grade ≥2)
  - fraction of referable cases in the top 20% of the list
  - workload to 95% sensitivity: the share of the list a grader must read, top down, to see 95% of referable cases
  - the same workload under random order (0.95 by expectation), for comparison
- Nothing is tuned on these numbers.

## ADR-018a — Pseudo-label student: apply the swap rule mechanically (2026-10-29 evening, before the experiment ran)
- **Status:** Accepted (user decision). Supersedes "record only" in ADR-018.
- **Comparator:** the app grader at decision time (after the ensemble decision). Its latest registry runs on IDRiD-val and APTOS-val are used.
- **Rule:** the three ADR-013 conditions. A pass switches the app grader; the change is reversible via `configs/app/app.json` history.

## ADR-021 — Pre-registered A4 lesion-to-grade fusion (2026-10-29, before any fusion result)
- **Features per image:**
  - app-grader regression score
  - log(1 + count) of MA and HE regions
  - number of FOV-centred image quadrants containing HE (0–4)
  - log(1 + area) of EX and SE (display px)
  - All lesion features use the app segmenter and post-processing after the A3 decision.
- **Model:** multinomial logistic regression (L2, C = 1.0, standardised features), predicting the ICDR stage.
- **Training data:** the fine-tuner's inner hold-out only (never trained on by the grader).
  - Images within structure-hash distance ≤42 of any DDR lesion-segmentation image (train, valid or test) are excluded, because the A3 segmenter may have trained on them.
  - DDR-test is excluded entirely.
- **Adopted only if all hold** (paired bootstrap, 2,000 resamples, against the app grader):
  1. The ADR-013 rule passes on IDRiD-val and APTOS-val.
  2. The Δ stage-1 recall CI on APTOS-val is above 0.
  3. Severe under-grading is not significantly increased (ADR-013 condition 3).
- **Integration:** an adopted fusion replaces only the stage. Calibration (ADR-019) is then re-fitted for the fused output.

## ADR-022 — Pre-registered R1 robustness test (inference only)
- **Sets:** IDRiD-val and APTOS-val; app grader and quality gate.
- **Degradations**, each applied to the original image:
  - Gaussian blur, σ = 0.2% and 0.5% of image width
  - brightness ×0.6 and ×0.35
  - contrast ×0.5
  - JPEG quality 50 and 30
  - downscale to long side 1280 and 640 px
  - rotation +10°
- **Reported per level:** QWK, referable sensitivity and specificity, fraction flagged by the quality gate, and fraction deferred (ADR-019 when calibrated). Nothing is tuned on these numbers.

## ADR-023 — Pre-registered R2 bad-input safety
- **Inputs:**
  - ≥60 locally generated non-fundus images: noise, gradients, checkerboards, solid colours, random shapes, rendered text "screenshots", natural-like textures
  - heavily blurred (σ = 2% of width) versions of IDRiD dev-train images
  - very dark (×0.15) versions of IDRiD dev-train images
- **Required behaviour:** each image is rejected, flagged by the quality gate, or deferred. A confident stage on any of them is a failure.
- **If any fail:** the gate thresholds are refitted on these training-side images only, then re-tested on a fresh seed.

## ADR-024 — Pre-registered R3 Grad-CAM shortcut audit
- **Sets:** IDRiD-val and APTOS-val; app grader. The peak is the maximum of the display-size Grad-CAM map. It is classified, in this order, as:
  1. **border:** within 5% of the FOV radius from the FOV edge
  2. **optic disc:** within 1.5 disc radii of the located disc centre
  3. **glare:** the mean green value in a 15 px window around the peak lies above the 99th percentile of FOV green values
  4. otherwise **retina**
- **Warning rule:** if border + disc + glare exceed 10% on either set, the Case View shows a plain-language warning for images whose peak falls in those regions.

## ADR-025 — R4 quality-gate validation on DDR ungradable images (training side only)
- **Data:** DDR grading train split, label 5 (ungradable) against an equal-size random sample (seed 17) of labels 0–4 from the same split.
- **Reported:** the quality gate's flag rate on each group (sensitivity and specificity for ungradable). Validation only; nothing is fitted on it.

## ADR-026 — Pre-registered scorecard targets (2026-10-30, before any of the methods below ran)
- **Status:** Accepted. `results/SCORECARD.md` is generated from the registry and decision files by `tools/scorecard.py` and checked by the consistency test.
- **Hard rule:** nothing is tuned, selected or fitted on IDRiD-val, APTOS-val or any locked set to reach a target. A missed target is reported as missed.
- **Grading targets:** APTOS-val QWK ≥ 0.92; macro-F1 ≥ 0.70; stage-1 recall ≥ 55%; stage-4 recall ≥ 70%; severe under-grading ≤ the current 1.6%. IDRiD-val QWK ≥ 0.89.
- **Segmentation targets** (IDRiD 5-fold CV, pixel AUPR): MA ≥ 0.40, HE ≥ 0.60, EX ≥ 0.80, SE ≥ 0.60. On DDR-test, each lesion's AUPR is above v0.1 (paired over images, bootstrap CI > 0). Grade-0 false-positive regions ≤ pp_v2.
- **External target:** referable AUROC ≥ 0.90 on each external set (ADR-034).

## ADR-027 — S1: thresholds for macro-F1 (inner hold-out only)
- **Candidate:** the app grader with its four regression thresholds re-fitted to maximise macro-F1 on the fine-tuner's inner hold-out. Coordinate search on a 0.01 grid, starting from the current thresholds.
- **Adopted if,** by paired bootstrap against the app grader on IDRiD-val and APTOS-val:
  1. the Δmacro-F1 CI is above 0 on at least one set;
  2. the ΔQWK CI lower bound is above −0.02 on both;
  3. severe under-grading is not significantly increased.

## ADR-028 — S2/S3: stage specialists (cascade)
- **S2, stage 0 vs 1:** ConvNeXt-T at 768 px, binary. Trained on the mixed pool's training side, images of grade ≤1 only (same inner split). It is applied only when the system stage is 0 or 1. Its threshold gives 90% specificity for grade 0 on the inner hold-out.
- **S3, stage 3 vs 4:** ConvNeXt-T at 512 px, binary, grade ≥3 images, class 4 oversampled to balance. It is applied only when the system stage is 3 or 4. Its threshold maximises balanced accuracy on the inner hold-out.
- **Adopted if** (each specialist separately, against the system without it):
  1. the stage-1 (S2) or stage-4 (S3) recall gain CI on APTOS-val is above 0;
  2. the ΔQWK CI lower bound is above −0.02 on both sets;
  3. severe under-grading is not significantly increased.

## ADR-029 — S4: ordinal (CORN) head
- **Candidate:** ConvNeXt-T at 384 px with a CORN ordinal head (4 conditional binary logits) and class-balanced weighting (sqrt). The backbone is warm-started from reg384 seed 17. The rest of the recipe is unchanged; the stage is predicted as the sum of P > 0.5.
- **Adopted** via the ADR-013 rule against the app grader.

## ADR-030 — Test-time augmentation (fixed a priori)
- **TTA set:** original + horizontal flip + rotations of ±8°. Regression scores are averaged.
- **Adopted** via the ADR-013 rule against the final system without TTA. It is applied last, once.

## ADR-031 — Segmentation upgrades and a lesion-level metric
- **Lesion-level metric (reported, not used for selection):** connected-component detection sensitivity at 1, 2, 4 and 8 false-positive components per image (FROC-style), per lesion, on IDRiD-val and DDR-test. A predicted component counts as a hit if it overlaps a ground-truth component.
- **Candidates, in priority order** (stop when ~10 GPU-hours are used; record what was skipped):
  1. A3 fold ensemble (mean of the 5 CV fold models) + horizontal-flip TTA. Inference only.
  2. MA variant: green-channel CLAHE input at full resolution, small-object-weighted loss (Tversky β = 0.7), MA channel only.
  3. Loss upgrade: focal (γ = 2) + Dice per lesion.
  4. Encoder upgrade: U-Net with an ImageNet ConvNeXt-T encoder, only if the weights are cached and it fits in 4 GB.
- **Each candidate** gets post-processing re-selected on IDRiD CV out-of-fold maps with the grade-0 FP constraint (ADR-011). It is adopted per lesion by the ADR-016 rule against the then-current app segmenter.

## ADR-032 — Explanation faithfulness test (pre-registered)
- **Images:** IDRiD-val and APTOS-val images the app grades ≥ 2.
- **Intervention:** the lesion regions the explanation cites (its referenced lesions' segmented components) are inpainted with OpenCV Telea on a 5 px dilated mask.
- **Control:** an equal total area of randomly placed discs inside the FOV and outside any segmented lesion (seed 17), inpainted the same way.
- **Outcome:** the drop in grader regression score.
- **Test:** a Wilcoxon signed-rank test, cited drop vs control drop, one-sided, α = 0.05 per set. The claim "the explanation reflects what drove the decision" is made only if both sets are significant.

## ADR-033 — Pipeline composition and worklist scale
- **One grading system** in `configs/app/app.json`: base grader → thresholds (S1) → fusion (A4) → specialists (S2, S3) → TTA. Each part is optional and adopted by its own rule. Calibration (ADR-019) is re-fitted after any change to the base score, and is marked unavailable when fusion or specialists change the stage.
- **Worklist scale check:** 500 synthetic cases from dev-train images in a throwaway store. Measured: render time of the worklist (no target tuning).

## ADR-034 — External validation (locked now)
- **Sets:**
  - the IDRiD clean test (102, already locked)
  - DeepDRiD regular fundus images, from the official GitHub release. The licence is recorded before use. It is audited (IDs, labels, duplicates, leak check against all training and validation data by structure hash, distance ≤42) and then locked: no training, tuning, selection or display.
- **Procedure:** after all decisions above, tag `rc-1` and record the checksums. Then run ONE evaluation per set:
  - QWK and macro-F1
  - per-grade recall with CIs
  - within-one-stage agreement
  - referable AUROC, with sensitivity and specificity at the app operating point
  - decision-changing errors (referable ↔ non-referable)
  - deferral rate
  - DeepDRiD only: quality-gate agreement with the DeepDRiD quality labels
- **Reporting:** whatever the result, with no changes afterwards. Messidor-2 follows later on the same rc-1.

## ADR-031a / ADR-032a — Implementation clarifications (2026-10-30, before any of these ran)
- **Inpainting (ADR-032):** OpenCV is not installed and packages are not added. Regions are filled by harmonic inpainting: iterative 3×3 mean diffusion from the boundary, 200 iterations per colour channel, scipy only. The same method is used for the cited and the control regions.
- **MA variant input (ADR-031):** scikit-image is not installed, so "CLAHE" is replaced by a local contrast normalisation of the green channel: (G − Gaussian(G, σ = 8 px)) / local std (σ = 8 px), clipped to ±3 and rescaled to 0–255. It is computed at the 1536-px FOV scale. Everything else is as in ADR-031.
- **Fold-ensemble CV estimate (ADR-031):** a 5-fold ensemble contains the fold model trained on each held-out image, so its CV maps are not out-of-fold. Its CV condition (ADR-016 rule 1) therefore uses the out-of-fold model with horizontal-flip TTA. IDRiD-val and DDR-test use the full 5-model ensemble with TTA.

## ADR-029a / ADR-031b — Clarifications (2026-10-30, before running)
- **CORN stage (ADR-029):** the stage is the expected rank, Σ_k Π_{j≤k} σ(logit_j), cut at 0.5/1.5/2.5/3.5. That keeps one continuous score for margins, calibration and Grad-CAM. CORN early stopping uses inner-hold-out QWK.
- **Segmentation GPU budget (ADR-031):** A3 itself takes about 6.5 GPU-hours, so the fold ensemble + TTA (about 0.5 h) and the MA variant (about 6 h) already exceed the ~10 h budget. As pre-registered, the loss upgrade and the encoder upgrade are **skipped** and recorded as skipped.

## ADR-034a — DeepDRiD protocol details (2026-10-30, before any DeepDRiD image was analysed)
- **Source:** github.com/deepdrdoc/DeepDRiD, `regular_fundus_images` only (sparse checkout). Licence: CC BY-SA 4.0.
- **Locked set:** all 2,000 regular images (training 1,200 + validation 400 + online-challenge test 400 with its label sheets), from 500 patients, 2 views per eye. None is used for training, tuning, selection or display.
- **Label:** the eye-level DR grade of each image's eye (left_eye_DR_Level / right_eye_DR_Level; Challenge1 sheet for the test part). Grade 5 ("cannot be graded") is excluded from grading metrics and counted as poor quality.
- **Quality-gate agreement:** "Overall quality" (1 = good enough for diagnosis) against the app's verdict (usable and not rejected). Reported as accuracy, and as the flag rate among images labelled poor.
- **CIs:** bootstrap over **patients** (2,000 resamples), because the images of one patient are correlated. The IDRiD clean test uses per-image bootstrap.
- **Audit before locking:**
  - every label row has an image file and vice versa
  - grade ranges are valid
  - within-set near-duplicates (structure hash ≤32) are reported
  - leak check against every image used for training or validation (IDRiD all, APTOS train/val/test, MMRDR, DDR lesion sets; distance ≤42); matches are removed from the locked set and listed

## ADR-035 — DeepDRiD aggregation (pre-registered 2026-10-30, before any DeepDRiD image is analysed)
- **Primary:** image-level metrics as in ADR-034a, with CIs bootstrapped by patient. No other aggregation may be reported as primary later.
- **Secondary, eye level:** an eye's score is the MAX of its two images' continuous system scores, mapped through the app's thresholds/system to a stage.
  - If one image is rejected or flagged by the quality gate, the other image is used.
  - If both are, the eye counts as deferred/ungradable and enters the deferral rate.
  - Specialists (if adopted) are applied to the image with the max score.
- **Secondary, patient level:** a patient is referable if their worse eye is referable.
- **Grade 5 and quality labels:** handled as in ADR-034a. The eye-level label is the eye's DeepDRiD grade; eyes graded 5 are excluded from the grading metrics.

## ADR-036 — Conditional segmentation upgrades, per lesion (2026-10-30; supersedes the budget skip in ADR-031b)
- **Order:** A3 decision → fold ensemble + flip TTA → MA variant (MA only).
- **Then, for each lesion whose app method still misses its ADR-026 CV target** (MA 0.40, HE 0.60, EX 0.80, SE 0.60) **by more than 0.05:**
  1. **Loss upgrade:** focal (γ = 2) + Dice on that lesion's channel, plus the A3 BCE + Dice on the others (5 folds).
  2. **Encoder upgrade, only if still more than 0.05 short:** U-Net with an ImageNet ConvNeXt-T encoder (timm weights; cached, else EfficientNet-B3 if cached; else skipped and recorded). AMP + gradient checkpointing.
- **Adoption:** each step is adopted only through the per-lesion rule (ADR-016 conditions) against the app's current method for that lesion. Post-processing is re-selected on training-side CV maps with the grade-0 FP constraint.
- **Trigger:** read mechanically from the registry by `tools/seg_trigger.py`. A missed target is recorded as missed.

## ADR-037 — Conditional EyePACS 2015 (2026-10-30)
- **Trigger:** after S2, S3, S4 and the ensemble decision, the app system's APTOS-val stage-1 recall < 55% **or** stage-4 recall < 70% (latest registry run). Evaluated by `tools/eyepacs_trigger.py`; not triggered → recorded and skipped.
- **If triggered:**
  1. Check free disk: the archive + extraction must leave ≥40 GB free; otherwise stop and record.
  2. Download the train images + trainLabels via the Kaggle CLI only (competition `diabetic-retinopathy-detection`; the user accepted its rules). Verify the archives and extract.
  3. Audit: the calibrated-hash leak check against every validation and locked set (IDRiD-val, APTOS-val, IDRiD clean test, DeepDRiD, Messidor-2 if present) at ≤42, plus duplicates and the grade distribution. Leak matches are removed.
  4. Add to the grading pool as a 4th dataset with dataset-balanced sampling. Retrain the best grading system's base grader (same recipe, seed 17) and evaluate through the existing rules.
- **Recorded:** EyePACS labels are single-grader (noisy).
- **Token:** never read, printed, copied or committed; the Kaggle CLI uses it directly.

## ADR-038 — Queue order and freeze detection (2026-10-30)
- **Order:** A3 → DME refit → S1 → segmentation ensemble + TTA → MA variant → seed 41 + ensemble decision → S2 → S3 → S4 → conditional EyePACS → conditional segmentation loss/encoder upgrades → DME refit if the segmenter changed → A4 fusion → pseudo-label → DeepDRiD re-audit → faithfulness → R2/R1/R3/R4 → final TTA → timing → rc-1 readiness check.
- **Freeze detection:** a gap of more than 15 minutes between GPU-monitor readings (`queue/logs/gpu.csv`) is a freeze. Freezes are listed in `results/freezes.json` and in each report.

## ADR-039 — Approach V2: selective routing hypothesis, pre-registered (2026-10-30, before any Step-2 result)
- **Status:** Accepted. The architecture is frozen in `docs/APPROACH_V2.md`.
- **Referable DR (primary):** ICDR grade ≥ 2, DR only, on every dataset.
  - **Secondary (IDRiD only, where labelled):** grade ≥ 2 OR IDRiD macular-oedema risk ≥ 1.
  - This is a research convention (ICO 2017 / published DR-AI practice), not universal; other programmes define referral differently.
- **Urgent:** "expedited specialist review recommended", meaning suspected severe/proliferative DR (high global score) or central-vision concern. Timelines belong to the local programme, not to the AI. The AI never "confirms PDR".
- **Output semantics** (`docs/APPROACH_V2.md`):
  - Internal state ROUTINE_RESCREEN_ELIGIBLE; no "normal / healthy / cleared".
  - Clinician text: "No referable diabetic retinopathy detected by AI in gradable images of both eyes."
  - Patient text: "This photo check did not find diabetic eye damage that needs a specialist now. It is not a full eye examination. Come back for your next check, or sooner if your vision changes."
- **Primary metric — safe screening coverage at miss rate m:**
  - **Definitions:**
    - Coverage = units routed ROUTINE / all screened units, **including** ungradable/rejected units.
    - Miss rate = referable units routed ROUTINE / all referable units.
  - **Thresholds:** operating thresholds are chosen **only** on the fine-tuner's internal hold-out (the largest threshold whose hold-out miss rate is ≤ m). IDRiD-val and APTOS-val are used only to **verify**.
  - **Statistics:** miss rate with an exact Clopper–Pearson 95% upper bound; coverage with a bootstrap 95% CI (2,000 resamples).
  - **Illustrative levels:** m = 5%, 2.5% and 1%. The real operating point is set by clinical governance, not by this project.
  - **Context, reported alongside:**
    - sensitivity for referable DR (= 1 − miss rate among gradable units)
    - specificity (non-referable units routed routine / all non-referable)
    - NPV of the routine pile
    - review rate (= 1 − coverage)
  - **Rule-of-three limit:** with n referable units and zero misses, the 95% upper bound is ≈ 3/n. IDRiD-val has n = 63 (≈ 4.8%), APTOS-val n = 201 (≈ 1.5%). The exact bounds are reported, including which levels each set cannot certify.
- **Units:** in Step 2, images; patient-level analysis is impossible on development data (no eye pairs) and is deferred to the locked DeepDRiD / Messidor-2 evaluation.
- **Step-2 baseline policies** (thresholds fitted on the internal hold-out; P(referable) = logistic calibration of the regression score on the internal hold-out, isotonic as a secondary check):
  - **(a)** route ROUTINE iff P(referable) < t_a.
  - **(b)** (a) AND the quality gate passes. Rejected or flagged images are never routine and stay in the denominator. t_b is fitted on the hold-out with the gate applied.
  - **(c)** (b) AND margin: the ADR-019 calibrated stage confidence ≥ τ (in-domain certainty about the stage), with t_c fitted on the hold-out with gate + margin applied.
- **Falsification:**
  - **Selective routing is ABANDONED as the central framing if either holds:**
    1. Safe coverage at the 2.5% level is near zero (bootstrap CI includes 0) on **both** validation sets.
    2. Verified validation miss rates exceed the target by more than the pre-set tolerance. Tolerance: the observed validation miss rate at the 2.5% level must not exceed 2.5% + 2.0 percentage points (i.e. ≤ 4.5%) on either set. Exceeding it on a set counts as failing verification on that set.
  - **Separate referable head:** adopt only if the Δcoverage CI is above 0 on ≥ 1 validation set and its lower bound is above −0.03 on the other.
  - **Disagreement:** abandon if the enrichment relative-risk CI includes 1, or if there is no incremental coverage gain over margin-based routing.
  - **OOD score:** abandon if the known-shift AUROC is < 0.70, or if there is no reduction in errors among routed cases.
  - **Ensemble:** abandon if there is no coverage gain beyond the single model.
- **Pending queue decisions** keep their already pre-registered rules unchanged; the coverage curve is added as a **reported, non-blocking** metric for each.
- **Pinned Step-2 baseline:** the current app grader `finetune:models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt`.
  - Checkpoint SHA-256 `acf53697500919cf7c281652c10b12c48e77896ed366a7383a78a432cbef37a1`.
  - `configs/app/app.json` SHA-256 `687d0abd7a51f5cb7879caeec61bfcf6743c4c429fbafda14b38bfad95e57c4d` (no system parts).
  - Calibration file SHA-256 `146e7ceaaa6b83ea818c4df4046e04087c86658b26dc5edf2a976758a2bbe244` (τ = 0.55).
  - Commit `b7c2685`.
  - Step 2 uses this checkpoint even if the queue later changes the app grader.

## ADR-040 — Step 3 decision layer: operating point and rules (2026-10-30, user GO; before implementation)
- **Status:** Accepted.
- **Operating point:** policy (c) from ADR-039.
  - **Default: target referable miss rate 2.5%**; configurable to 5% in the app settings.
  - **Rationale:** 2.5% costs only 1–2 points of coverage against 5% (APTOS-val 50.8% vs 52.3%; IDRiD-val 37.6% vs 39.6%).
  - **Frozen thresholds** (internal hold-out, never refitted on validation): P(referable) < 0.1360 (score < 0.8608) at 2.5%; P(referable) < 0.3174 (score < 1.2080) at 5%. P(referable) = the stored Platt map (identical to Step 2's fit); τ = 0.55.
  - **Validity:** only for the pinned grader (checkpoint `acf53697…`). If the app grading system differs, routing is disabled: nothing is ROUTINE, and every otherwise-routine image becomes CLINICIAN_REVIEW ("routine routing not validated for the current model").
- **Required wording:** "target referable miss rate 2.5%; verified upper bound 2.7% on APTOS-val (development data); not yet validated on external data". Never "certified" or "safe" without that qualifier. The framing is "AI-assisted prioritisation with a routine-rescreening pile"; selective routing becomes the headline only after the locked DeepDRiD patient-level evaluation.
- **Image (eye) states, first match wins:**
  1. **RETAKE:** rejected, or quality gate fails.
  2. **URGENT_REVIEW:** AI stage ≥ 3 (suspected severe / proliferative DR; never "confirmed") or macular-oedema risk "high" (central-vision concern). Lesion evidence only escalates.
  3. **REFERABLE:** AI stage 2.
  4. **CLINICIAN_REVIEW:** stage 0–1 but not routine-eligible. Reasons: confidence below τ; P(referable) above the routine threshold; intake flag; routing disabled; laterality mismatch; previous clinician referral.
  5. **ROUTINE_RESCREEN_ELIGIBLE:** policy (c) passes, with none of the above.
- **Intake (New screening):** at most two optional checkboxes, "Patient reports vision problems" and "Previous eye treatment / laser". Either one → CLINICIAN_REVIEW. No other questionnaire.
- **Patient aggregation (worse eye decides; priority URGENT > REFERABLE > CLINICIAN_REVIEW > RETAKE > ROUTINE):**
  - **Routine only if** both a right-eye and a left-eye image are present, gradable and routine-eligible.
  - **Missing eye:** INCOMPLETE_SCREENING, never routine.
  - **Ungradable eye:** RETAKE; after two ungradable attempts for that eye → CLINICIAN_REVIEW ("ungradable after retake: human grading").
  - **Contradictory eyes** (stages differ by ≥ 2): worse eye + asymmetry note.
  - **Laterality check:** the optic-disc position (disc right of the image centre → right eye) is compared with the recorded eye; a mismatch → operator prompt and CLINICIAN_REVIEW for that eye. This is a heuristic, not validated.
  - **Repeat visit:** the previous signed (reviewed) result is shown. A previous clinician referral (signed stage ≥ 2) is never auto-downgraded: a routine-eligible eye becomes CLINICIAN_REVIEW.
- **Worklist order:** URGENT_REVIEW → CLINICIAN_REVIEW → REFERABLE → RETAKE pending → ROUTINE_RESCREEN_ELIGIBLE (batch sign-off).
- **Wording:** "cleared", "normal" and "healthy" are removed from the UI, reports, explanations, docs and About; tests forbid them in user-facing text.

## ADR-041 — Step 4 experiments: operational pre-registration; GPU incident (2026-10-30, before any Step-4 result)
- **Status:** Accepted. Step 4 is authorised to **run, not to integrate**: nothing here changes the production decision path. Integration needs the user's explicit approval after the results.
- **GPU incident (recorded):** lid standby 13:20–13:29 → 510 nvlddmkm "Graphics FECS Exception" events 14:00–14:13 → A3 fold 2 stalled at ~18 W / 100% util on both attempts (no step-500 line in 90 min) → queue runner, A3 and the :8000 backend stopped at 16:50 on the user's instruction. No reboot happened. After stopping, a 60 s fp16 matmul load drew ~60 W (cap 59 W), 17.2 TFLOPS: the stall belonged to the stalled CUDA context, not the GPU. A3 (folds 2–4) is deferred by the user; `queue/jobs.yaml` is unchanged; the runner is not relaunched. Details: `queue/NOTES.md`.
- **GPU rule from now on:** while the queue trains, nothing else uses the GPU. Automated tests and scripts set `CUDA_VISIBLE_DEVICES=-1` inside Python before importing torch (an empty value from Git Bash does not reach Windows processes).
- **Common to all four experiments:**
  - **Comparator:** the pinned grader reg384 s17 (`acf53697…`) with policy (c) exactly as in ADR-039/040.
  - **Fitting:** every threshold, Platt map, margin→confidence isotonic and τ of an alternative is refitted **only on the fine-tuner's internal hold-out (2,813 images)** with the ADR-019 / ADR-039 procedures. IDRiD-val and APTOS-val only verify (development data).
  - **Statistics:** paired bootstrap over images (2,000 resamples, seed 17) for Δcoverage = coverage(alternative) − coverage(pinned policy c) at the same target; exact Clopper–Pearson upper bound for miss rates.
  - **ADOPT-candidate rule (coverage experiments a, c, d):** at the 2.5% level, the Δcoverage 95% CI is above 0 on ≥ 1 validation set and its lower bound is above −0.03 on the other, **and** the alternative's verified miss rate is ≤ 4.5% on both sets (ADR-039 tolerance). Otherwise ABANDON. The 5% level is reported, not decisive.
- **(c) Separate referable head:** ConvNeXt-T @384, same pool, inner split, sampler, schedule and seed 17 as the pinned grader; two outputs: the regression score (smooth L1) and a referable logit (BCE on grade ≥ 2), equal loss weights, fixed before training (`finetune_mixed.py --head regbin`). P(referable) = Platt map of the referable logit on the hold-out; stage and confidence from the model's own score. **Primary comparison:** head P(referable) vs the pinned grader's derived P(referable) (what adoption would change). Secondary (reported): the same model's head vs its own derived P(referable).
- **(d) Ensemble value for routing:** seed runs that exist: reg384 s17 + s23 (s41 was never trained; the queue was stopped). Score = mean of the two; thresholds = mean of the members' (as `FinetunedGrader`); Platt, confidence and τ refitted on the hold-out.
- **(b) OOD score:** Mahalanobis distance on the pinned grader's 768-d pre-logit embedding, one Gaussian with Ledoit–Wolf shrinkage, fitted on the training side of the pool (pool minus the inner hold-out).
  - Known-shift test 1 (dataset): fit on the APTOS training side only; AUROC of IDRiD-val (shifted) vs APTOS-val.
  - Known-shift test 2 (synthetic): fit on the full training side; AUROC of degraded vs clean IDRiD-val + APTOS-val, pooled over four degradations applied to the 384-px input (Gaussian blur σ = 4 px; darkening ×0.35; Gaussian noise σ = 25/255; JPEG quality 5).
  - Routing use: gate = distance below the 95th percentile of the hold-out distances; added to policy (c) with the routing threshold refitted on the hold-out.
  - **ABANDON** if either known-shift AUROC is < 0.70, or if the gate does not reduce missed referable images among routed images (pooled over both validation sets, at 2.5% and 5% together).
- **(a) Global/local disagreement** (amended by the owner's Steps 4–7 prompt before any (a) result existed):
  - Segmenter = the app segmenter **v0.1** (see below).
  - Flag (among would-be-routine images only): HE + EX component count ≥ k_HEEX, **or** MA component count ≥ k_MA. MA alone triggers only when far above the healthy distribution: k_MA = the 99.5th percentile of MA counts on grade-0 training images (minimum 1).
  - Reference: grade-0 images on the training side (up to 300 per source dataset, seed 17). Candidates for k_HEEX: the 90th / 95th / 97.5th / 99th grade-0 percentile (minimum 1).
  - Referral budget: the flag may add at most 5% of all screened images to review on the hold-out at the 2.5% level; the most sensitive candidate within budget is chosen on the hold-out.
  - Report on IDRiD-val + APTOS-val among would-be-routine images (policy c): relative risk of referable in flagged vs unflagged (Katz 95% CI, +0.5 in empty cells), incremental coverage over policy (c) at 2.5% and 5% (flag applied, routing threshold refitted on the hold-out; paired bootstrap), extra review rate, and whether the flag catches any of the three known misses (IDRiD_208, IDRiD_270, APTOS d28bd830c171).
  - **ABANDON** if the pooled RR CI includes 1, or if the ADOPT-candidate rule on Δcoverage fails. v0.1 lesion quality limits this test.
- **(d) amended:** the owner's rule: "if fewer than 2 extra seeds exist, record not testable; do not train new seeds". Only s23 exists, so **(d) is NOT TESTABLE**. The two-member (s17 + s23) numbers are reported as descriptive only.
- **(e) Explanation faithfulness** (ADR-032/032a, inference only) and **(f) R1 robustness** (ADR-022, inference only, plus policy-(c) coverage, miss rate and quality-gate catch rate per degradation) are added to Step 4 by the owner, with their already pre-registered rules.
- **(c) GPU estimate:** about 100 min (the pinned s17 recipe took 92 min), below the owner's 3 h limit.
- **Integration (Step 5):** only "adopt" signals enter the decision rule, and only to escalate (never to permit routine). Thresholds refitted on the hold-out only.
- **Owner decisions recorded (2026-10-30):**
  - A3 segmentation is **stopped by owner decision** (GPU driver fault, priorities) and deferred. Its queue state is "cancelled", not failed.
  - The app segmenter for all Step 4–7 work is **v0.1**: SegFormer-B0 @512 HE/EX/SE `seg_Segformer_full512_bce_dice_s17.pt` (SHA-256 `04402be272a639bd8f2a9a89107d21b69efed28b424b0f8c510f7efee7459c0b`) + MA U-Net `ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.pt` (`a1221c966a69c145b0327aa3f25900985bf560e5011076b46baba35ed73178b2`) + `configs/postprocess/pp_v2.json` (`1f49fca58b0296a9e3aa82de868d0b23ea3477573ac5256cd5ce7e9a360c5e6e`).
  - Every queued job not part of Steps 4–7 is **cancelled, not failed** (`enabled: false` with the reason in `queue/jobs.yaml`). faithfulness, r1_robustness, benchmark_final and rc1_check run directly as Steps 4e, 4f, 6 and 7.
  - One GPU job at a time. (Disclosed: between 17:05 and ~17:25 the Step-4 embedding pass overlapped the referable-head training, before this rule arrived.)
- **Outputs:** `results/step4/*.json`, one registry row per experiment and set. No fundus images in outputs.

## ADR-042 — Step 4 verdicts and Step 5 integration (2026-10-30, after the Step-4 results)
- **Status:** Accepted. Results: `results/step4/step4_results.json`, `results/faithfulness.json`, `results/robustness/r1_robustness.json`; registry rows (task `step4`, `faithfulness`, `safety`). Development data only.
- **Comparator check:** the pinned policy (c) was re-run from the frozen `configs/routing/routing_v1.json` (Platt map + thresholds) and reproduces Step 2 exactly: IDRiD-val 37.6%, missed 2/63; APTOS-val 50.8%, missed 1/201 at 2.5%. Refitting the thresholds from the Step-4 score pass gives 0.13603 / 0.31675 instead of the frozen 0.13603 / 0.31741 (fp16 batch effects); recorded, not used.
- **Verdicts (pre-registered rules, ADR-039 / ADR-041):**
  - **(a) Disagreement: ABANDON.** The v0.1 segmenter marks many HE/EX regions on true grade-0 training images (90th percentile 22, 97.5th 57; n = 680), so the budget-limited threshold is ≥ 58 HE+EX regions (MA ≥ 60 regions). Among would-be-routine images it flags 2 (IDRiD-val) and 4 (APTOS-val), none referable; pooled RR 6.0 [0.34, 106] includes 1. Coverage at 2.5%: IDRiD −2.0 points [−5.0, 0.0], APTOS −0.8 [−1.5, −0.2]. It catches none of the three known misses (HE+EX 0, 2 and 7 regions). Limited by v0.1 lesion quality; to be re-run with a better segmenter.
  - **(b) OOD score: ABANDON.** Dataset-shift AUROC (IDRiD-val vs APTOS-val, fit on APTOS training) 0.62 < 0.70. Synthetic degradations pooled 0.85 (blur 1.00, JPEG q5 1.00, noise 0.92, darkening 0.48). Missed referable among routed images: 8 without and 8 with the gate.
  - **(c) Separate referable head: ABANDON.** Head vs pinned at 2.5%: IDRiD-val −3.0 points [−7.9, +2.0], missed 1/63; APTOS-val +4.8 [+2.7, +7.1] but missed 11/201 (5.5% > 4.5% tolerance). The same model's derived P(referable) vs pinned: −5.0 [−9.9, 0.0] and +0.2 [−1.0, +1.4]. Training: 15 epochs, best epoch 11, inner QWK 0.925; the run was interrupted after epoch 3 (session end) and resumed from its resume file.
  - **(d) Ensemble: NOT TESTABLE** (one extra seed; the owner's rule needs two). Descriptive two-run average at 2.5%: IDRiD +2.0 [0.0, +5.0], missed 3/63; APTOS +0.4 [−0.4, +1.4], missed 0/201.
  - **(e) Explanation faithfulness: ADOPT (claim supported).** Median score drop when the cited lesions are hidden vs an equal-area control: IDRiD-val 0.295 vs −0.016 (n = 59, p = 4.5e-6); APTOS-val 0.235 vs −0.013 (n = 221, p = 4.3e-17). The claim "the highlighted lesions drive the AI score" may be made, qualified as development data.
  - **(f) R1 robustness: REPORTED** (no adopt rule; `results/robustness/r1_robustness.json`). Policy (c) at 2.5%, referable routed to routine:
    - Clean: IDRiD-val 2/63 (coverage 37.6%), APTOS-val 1/201 (50.8%).
    - Strong blur (σ 0.5% of width), contrast ×0.5 and brightness ×0.35 are flagged by the quality gate on 70–100% of photos; coverage falls to 0–17%, misses 0. Fail-safe.
    - **Not caught by the gate:** IDRiD downscaled to 640 px: 4/63 missed (upper bound 15.5%), gate flagged 2%; IDRiD rotation 10° and blur σ 0.2%: 3/63 (13.3%). JPEG 50/30 and APTOS degradations stay at 0–2/63 and 0–1/201.
    - Grading: worst QWK IDRiD blur 0.5% 0.794 (clean 0.893), APTOS blur 0.5% 0.849 (clean 0.918).
    - Consequence (recorded, no rule changed): the routine pile is not validated for heavily downscaled photos. The About page states this; the quality gate is not refitted (that would be an unregistered change).
- **Step 5 (integration):** no routing signal passed, so **the decision path is unchanged** (policy c, 2.5% default). Nothing was in the decision path to remove. The negative results are shown on the About page ("What we tested before adding it") and in KEY_NUMBERS, generated from the result files (`backend/experiments.py`), with a consistency test. (e) changes no decision; it permits the explanation claim. No new review reason was added, so there are no new Simple/Clinical or Hindi strings.
- **Observation for (f), not a rule:** in (b), with the clean images' quality flags reused, policy (c) routed 36 noisy (σ = 25) and 19 JPEG-q5 referable images to routine at the 384-px input; R1 measures the real quality gate on degraded full images.

## ADR-043 — Step 7 locked evaluation protocol (pre-registered 2026-10-30, before rc-1 and before any locked image is analysed)
- **What is evaluated:** rc-1 for GRADING + ROUTING + QUALITY only, once per set, by `tools/locked_eval.py`, which refuses to run unless HEAD is exactly the tag `rc-1` with no tracked changes, and refuses a second run of a set. Every image goes through the app path: `Pipeline.analyze` → `assist.annotate` → `routing.eye_state` (2.5% default) → `routing.patient_state`. No threshold, rule or model changes afterwards, whatever the result.
- **IDRiD clean test (102):** image level: QWK, macro-F1, per-grade recall, within-one, referable sensitivity/specificity at the app's stage, referable AUROC (frozen Platt P(referable)), decision-changing errors, deferral rate, quality-flag rate; policy (c) image coverage and miss rate with the exact Clopper–Pearson upper bound. CIs: bootstrap by image (2,000, seed 17). Laterality is not recorded for IDRiD, so the laterality check is skipped.
- **DeepDRiD (locked manifest, 1,988 images, 500 patients; ADR-034a/035):**
  - **Primary, image level:** the same metrics, grade 5 ("cannot be graded") excluded from grading metrics; CIs bootstrapped by patient.
  - **Quality gate:** agreement with "Overall quality" (grade 5 counts as poor): accuracy, flag rate among poor, flag rate among good.
  - **Eye level (secondary, ADR-035):** the max-score gradable view gives the eye's stage.
  - **Patient level (ADR-040 states):** an eye's state is the worst state among its gradable views (a view needing a retake is ignored when the other view is gradable; both → RETAKE). Patient state = `routing.patient_state` (worse eye; a missing eye → INCOMPLETE). A patient is referable if their worse labelled eye is grade 2–4; patients with no labelled eye are excluded from the miss denominator but stay in coverage. Reported: patient coverage at 2.5% with a patient-bootstrap CI, missed referable patients with the exact upper bound, the state distribution, deferral rate.
- **Reserved:** the IDRiD segmentation locked test (27 images) is **not** evaluated now; it stays locked until a final segmenter exists. Messidor-2 is evaluated on the same rc-1 only when the owner says "Messidor-2 placed".

## ADR-044 — Step 6: timing and the CPU fallback (2026-10-30, measurement only)
- **CPU start-up crash, diagnosed without changing packages:**
  - Minimal reproduction: with `CUDA_VISIBLE_DEVICES=-1`, calling `torch.cuda.is_available()` and then constructing any layer crashes with an access violation (4/4). Without the probe 0/4; with the GPU visible 0/4. torch 2.11.0+cu128, Windows.
  - The app's `default_device()` made exactly that probe. Fix (code only): when `CUDA_VISIBLE_DEVICES` is `-1`, return "cpu" without probing. A/B on the full pipeline build: 6/6 crashes before, 0/6 after.
  - Not involved: thread count (OMP 1 also crashed with the probe), RAM/commit (14 GB free, commit 24/50 GB), duplicate OpenMP runtimes (torch's libiomp5md and sklearn's vcomp140 are both present but the crash follows the probe, not the import set). An earlier "reboot fixed it" impression came from a contaminated test (a scratch file named `bisect.py` shadowed the standard library); it is discarded.
  - **Root cause of the remaining crashes (found during the rc-1 readiness check):** the CPU-only test suite still crashed in 2 of 4 runs, and one CPU app instance crashed while idle. Windows logs every one of today's Python crashes with the faulting module `nvdxgdmal64.dll_unloaded` (NVIDIA user-mode driver). With the GPU hidden, **any** CUDA driver initialisation (the probe above, but also torch's autograd engine, which counts CUDA devices on the first backward pass, e.g. Grad-CAM) finds no device and unloads part of the driver while a callback stays registered, so the process faults later at a random moment.
  - Controlled test (CPU backward pass, then 40 s of CPU work): GPU hidden 2/4 crashes; GPU visible but unused 0/4. Full suite CPU-only with the GPU visible: 4/4 passed (90 tests), and nvidia-smi shows no Python process during the run.
  - **Decision:** CPU mode is selected with `RS_DEVICE=cpu` (new; `default_device()` honours it), not by hiding the GPU. Tests, the CPU benchmark and the CPU launch configuration use it. This replaces the ADR-041 rule "set CUDA_VISIBLE_DEVICES=-1 inside Python" (that rule itself caused crashes); the intent is kept: nothing else uses the GPU while the queue trains, verified with nvidia-smi.
  - **What is verified:** CPU-only analysis on this laptop with `RS_DEVICE=cpu`. **Not verified:** a machine with no NVIDIA GPU or driver (no driver DLL to unload, so this crash path should not exist there, but it is untested), and the GPU→CPU retry after an out-of-memory error. README states this.
  - Options for the owner (none taken): (1) keep `RS_DEVICE=cpu` (done); (2) an NVIDIA driver update via the NVIDIA app (owner action), then re-test with the GPU hidden; (3) a CPU-only torch wheel in a separate venv for CPU deployment (package change, needs approval).
- **Timing (`tools/benchmark.py`, `results/benchmark.json`; 10 IDRiD dev-train images as 5 two-eye patients after one warm-up; GPU = RTX 3050 4 GB laptop):**
  - Per image, GPU: 1.04 s (quality 0.05, grading + Grad-CAM 0.32, optic disc 0.05, fovea 0.11, segmentation 0.19, rest 0.33). CPU (`RS_DEVICE=cpu`): 1.42 s (grading 0.50, segmentation 0.37).
  - Per patient through the API (two eyes, routing, report): GPU 2.17 s (max 2.31); CPU 2.99 s (max 3.11).
  - Peak RAM: GPU process 1.8 GB, CPU process 1.5 GB. Peak VRAM allocated 363 MB. Model load: 0.9 s GPU, 0.6 s CPU (files cached).
  - No optimisation was attempted.
- **Observation from the screenshot seeding (not a rule change):** the macular-oedema rule ("yellow deposits near the centre of vision", v0.1 exudate masks) escalated 5 of ~20 IDRiD-val grade-0 images tried to URGENT_REVIEW. It is escalate-only (safe direction) but lowers the routine pile; the Step-2 coverage numbers do not include this rule. The locked evaluation measures the full app path, so it does.

## ADR-045 — rc-1 freeze record (2026-10-30, before the tag and before any locked image is analysed)
- **Status:** Accepted. Tag `rc-1` is placed on the commit that adds this entry. Nothing in the system changes after the tag; only outputs under `results/` (registry rows, run folders, locked results) may follow it. The owner's uncommitted notebook edit (`notebooks/01_IDRiD_dataset_understanding.ipynb`, not loaded by the app) is left as it is; the guard allows `notebooks/` and prints it.
- **Preconditions met:** Steps 4–6 done (ADR-041..044); `tools/rc1_check.py` READY (preflight, reproduce and 90 tests pass with `RS_DEVICE=cpu`; owner-cancelled jobs listed, none failed); screenshots in `results/screenshots/step3_4/`; KEY_NUMBERS and SCORECARD equal a fresh generation.
- **System:** app `v0.3 (grader convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt)`; grader reg384 s17; segmenter v0.1 (SegFormer HE/EX/SE + MA U-Net + pp_v2); no specialists, fusion or TTA; calibration ADR-019 (τ = 0.55).
- **Routing:** policy (c), `configs/routing/routing_v1.json` SHA-256 `e7466e999cdd9fd8be046dd513938b6b287bf6a4dcd7204d95d500b0ed36ada4`; **default operating point 2.5%** (threshold P(referable) < 0.13603); 5% selectable.
- **DME rule:** `configs/landmarks/dme_rule_v1.json` SHA-256 `48424cfc93679b6c41d700fd798f54c69bdb12d847a58d7db3cf6ae9efa79abd`.
- **Checksums recorded by `preflight.py --record` (`configs/app/checksums.json`):**
  - `configs/app/app.json`: `687d0abd7a51f5cb7879caeec61bfcf6743c4c429fbafda14b38bfad95e57c4d`
  - `configs/calibration/app_grader.json`: `146e7ceaaa6b83ea818c4df4046e04087c86658b26dc5edf2a976758a2bbe244`
  - `configs/landmarks/fovea_v1.json`: `1005d7d6de90dbd10503c15d8411cc307691b96523879f5549040e5cd0eced63`
  - `configs/postprocess/pp_v2.json`: `1f49fca58b0296a9e3aa82de868d0b23ea3477573ac5256cd5ce7e9a360c5e6e`
  - `configs/quality/quality_v1.json`: `e91e084a8edd5542af81441759de0ec5379c4e8214793f0fa9f0edd087d6a9c5`
  - `design/tokens.json`: `7e78964b4a1920e794d714e7f581ca6dc841e683e5014fc8f60ff8fb714f79cd`
  - `models/checkpoints/model_selection/ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.pt`: `a1221c966a69c145b0327aa3f25900985bf560e5011076b46baba35ed73178b2`
  - `models/checkpoints/model_selection/seg_Segformer_full512_bce_dice_s17.pt`: `04402be272a639bd8f2a9a89107d21b69efed28b424b0f8c510f7efee7459c0b`
  - `models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.json`: `25f79af47a5920830a9bd865215630e821878da126a73397e725ad8de734bf09`
  - `models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt`: `acf53697500919cf7c281652c10b12c48e77896ed366a7383a78a432cbef37a1`
  - `review/hindi_review.csv`: `f0e8cfa5b9a5b4ffe91289363ad362acc931f873a5db0c939d61bc9b2f35a983`
- **Environment:** torch 2.11.0+cu128, timm 1.0.30, numpy 2.4.6, Python 3.11.3, Windows 11, RTX 3050 4 GB (driver 572.40).
- **Locked evaluation:** ADR-043, once per set, IDRiD clean test then DeepDRiD. The IDRiD segmentation test (27) stays locked; Messidor-2 waits for the owner.

## ADR-046 — Locked evaluation of rc-1: results (2026-10-30; reported as measured, nothing changed afterwards)
- **Run:** `tools/locked_eval.py` on HEAD = tag `rc-1` (`564c7b7`), GPU, one set at a time. Results: `results/locked/idrid_test.json`, `results/locked/deepdrid.json` (+ per-image `.jsonl`), registry task `locked`.
- **Process deviations (disclosed):**
  1. The first IDRiD attempt was refused by the guard before any image was analysed: its status parsing dropped the first character of a path, so the owner's notebook edit looked like a system change. The evaluation ran from a scratch copy of the tool that differs only in that line (and in `ROOT`), with HEAD on `rc-1`; the same fix is committed after the tag.
  2. DeepDRiD: all 1,988 images were analysed once; the summary step then failed on a variable renamed in a refactor (`len(pat)`). The fix was applied to the scratch copy and the summary recomputed from the saved per-image records (no image analysed twice). My `sed` briefly touched the tracked tool too; the guard refused, the file was restored to rc-1, and the summary run went through.
- **IDRiD clean test (102 images, per-image bootstrap):**
  - Grading: QWK 0.816 [0.731, 0.883]; macro-F1 0.495; within one stage 90.2%; referable sensitivity 90.5% [0.825, 0.969], specificity 89.7% [0.794, 0.978]; AUROC 0.943. Per-grade recall 0–4: 0.88, 0.00, 0.69, 0.50, 0.38. Decision-changing errors: 6 referable called non-referable, 4 the reverse. Deferral 15.7%.
  - **Routing at 2.5% (images): coverage 33.3% [0.235, 0.422]; referable routed to routine 5/63 = 7.9%, exact upper bound 17.6%. This misses the 2.5% target and the ADR-039 4.5% tolerance.**
  - The five misses (descriptive): IDRiD_060 grade 3, and IDRiD_076/079/081/084 grade 2; all were confident AI stage-0 calls (score ≈ 0–0.13, confidence 0.78–0.96); three carry IDRiD macular-oedema grade 2 that the app's DME rule rated "low".
- **DeepDRiD (1,988 images, 500 patients; CIs bootstrapped by patient):**
  - Image grading (primary; 1977 images with grade 0–4): QWK 0.780 [0.753, 0.806]; referable sensitivity 93.0% [0.909, 0.949], specificity 84.2% [0.815, 0.868]; AUROC 0.946; per-grade recall 0–4: 0.58, 0.44, 0.76, 0.36, 0.64.
  - Image routing at 2.5%: coverage 23.9% [0.213, 0.267]; referable routed to routine 9/856 = 1.1%, upper bound 2.0% (within target). Deferral 14.3%; quality-flag rate 10.5%.
  - Eye level (secondary): QWK 0.762; referable sensitivity 97.8%, specificity 79.3%; 52 eyes ungradable.
  - **Patient level at 2.5%: coverage 7.0% [0.050, 0.094] (35/500); referable patients routed to routine 0/248, exact upper bound 1.5%.** States: {'URGENT_REVIEW': 285, 'REFERABLE': 76, 'CLINICIAN_REVIEW': 89, 'RETAKE': 15, 'INCOMPLETE_SCREENING': 0, 'ROUTINE_RESCREEN_ELIGIBLE': 35}.
  - Quality gate vs DeepDRiD "Overall quality" (grade 5 = poor): agreement 53.6%; flags 16.3% of 1061 poor images and 3.8% of 927 good ones.
- **Reading (no change made):** grading generalises with a moderate drop (QWK 0.89/0.92 on validation → 0.82 IDRiD test, 0.78 DeepDRiD). The routine pile was safe on DeepDRiD (0 of 248 referable patients) but small at patient level (7%), because 57% of patients went to urgent review (stage ≥ 3 or the DME rule) and either eye blocks routine. On the IDRiD test the pile missed 5/63, including one grade 3: confident stage-0 errors are not caught by policy (c). The quality gate barely agrees with DeepDRiD's quality labels. The headline stays "AI-assisted prioritisation with a routine-rescreening pile"; selective routing is not claimed as validated.

## Unattended queue (2026-10-29)
- GPU jobs run from `queue/jobs.yaml` via `tools/gpu_queue.py`. Every decision inside it applies only ADR-013/015/016/017.
- **Order:** A2 swap → A3 → DME refit → A2 seeds → pseudo-label.
  - A job whose code is not yet written is disabled. The queue runs the next enabled job instead, so the GPU never idles.
  - A3 is enabled as soon as its training script is tested, and it runs after the job in progress.

## Pending decisions (to be logged when evidence exists)
- Input resolution for grading (S2/S3)
- Grading loss (CE vs ordinal) (S2)
- Segmentation architecture, resolution and thresholds (S6)
- Calibration method and abstention threshold (S8)
- Attribution method for the chosen backbone (S9)
- Quality-gate thresholds (S7)
