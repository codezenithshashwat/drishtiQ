# DR Screening Decision-Support: Research & Engineering Blueprint v2

Status: **PROPOSAL, awaiting team approval.** No code was written for this document.
Date: 2026-10-28. Supersedes nothing; extends `DR_ARCHITECTURE_RECOMMENDATION.md`.

Evidence tags used throughout:
- **[E]** our experiment (file path given)
- **[P]** published, verified by us from a primary source this session
- **[P?]** published, recalled but **not re-verified this session**. Verify before putting it on a slide.
- **[H]** our hypothesis (untested)
- **[C]** constraint (hardware, time, licence)

Inputs read: the official Problem Statement 14 text; this repo's audit and model-selection docs and metrics; the MMRDR Scientific Data paper (PMC13102964) and figshare record; the RETFound Nature paper (Europe PMC full text) and the official repo README; the MMRDR third-party repo README; secondary search results (DDR, Messidor-2, RETFound-Green, the generalist-vs-specialist preprint, ViT XAI).
**Not read: neither shared research-conversation link could be retrieved (one showed only a truncated title, one returned 403).** Treat any claim that exists only in that conversation as unverified until it is pasted in.

---

## 1. Executive assessment

**Data hygiene is excellent. Modelling evidence is weak, and weaker than the current docs imply.**

1. **The IDRiD audit is a real asset.** It found 6 duplicate groups, 4 label-conflicting groups and cross-split leakage, with a reproducible clean protocol (404/102). Few teams will have this. It is our most defensible contribution today.
2. **The model-selection study was budget-starved, so its *negative* results are confounded.** Fine-tuning ran **6 epochs** at a last-stage-only setting. Segmentation trained for **6 epochs on 40 images** and validated on **10 images**, at a fixed 0.5 threshold with no threshold tuning (`configs/experiments/*.json`). The following claims are therefore **not supported**:
   - "fine-tuning doesn't help"
   - "larger inputs don't help"
   - "patches are worse than full images"

   The only supported statement is: *under a 6-epoch screen, these did not help*. The docs already say this in places; the slides must too.
3. **Grade 1 cannot be studied statistically on IDRiD.** There are 18 clean training images and 5 clean test images. The 3/18 = 16.7% recall has a Wilson 95% CI of about **5.8%–39%**. On the test set, each Grade-1 image moves recall by 20 points. **No intervention can be shown to fix Grade 1 using IDRiD alone.** This is the single strongest argument for a larger graded dataset, and it matters more than RETFound does.
4. **Calibration is poor:** ECE is 0.21–0.25 in OOF predictions ([E] `selected_grading_OOF_metrics.csv`). Any confidence display today would be misleading.
5. **Our frozen ConvNeXt already matches RETFound's paper-reported IDRiD AUROC.**
   - [E] OOF macro one-vs-rest AUROC is 0.821–0.825.
   - [P] the RETFound paper reports IDRiD AUROC 0.822 (95% CI 0.815–0.829).

   The splits and protocols differ, so this is *not* a head-to-head comparison. It is still a warning: **do not assume RETFound wins.**
6. **[P] At MMRDR scale, RETFound did not beat ResNet-50.** On MMRDR-CFP, fine-tuned RETFound scored accuracy 0.822 / F1 0.714, versus ResNet-50 at 0.823 / 0.702. Prediction [H]: any RETFound advantage will show up in the *low-data* regime (IDRiD), not at 11k images.
7. **The hardware constraint is binding [C].** We have an RTX 3050 Laptop with 4 GB VRAM. RETFound is ViT-Large (~304M params). Linear probing is feasible locally (fp16 feature extraction). Full fine-tuning is **not** feasible locally, so it needs Kaggle or Colab (T4/P100, 16 GB) or partial/LoRA tuning. Deployment of ViT-L on CPU is slow. This pushes us toward checking a small retinal model (RETFound-Green, ViT-S) as well.

**Bottom line:** do the next stage, data acquisition and a cross-dataset audit, then re-establish a *properly trained* baseline before any RETFound claim.

---

## 2. What we have done well

- Immutable raw data, hashing, and byte-for-byte reproducible manifests.
- Duplicate and conflict detection with a conservative policy: quarantine, don't relabel.
- "Missing mask ≠ negative" enforced in training code.
- A locked 102-image test set that has never been touched.
- A resolution experiment quantifying MA component loss (35.5% at width 224, 1.3% at 512, 0.06% at 1024) [E].
- Honest negative results recorded, with evidence codes.
- Ordinal-aware metrics (QWK, MAE, severe under-grading rate) already in the scorecard.

## 3. What is scientifically weak or unresolved

| # | Weakness | Why it matters | Fix (stage) |
|---|---|---|---|
| W1 | 6-epoch screens, 40-image seg training, 10-image seg validation | Negative conclusions are confounded with under-training | Convergence-checked "strong baseline" (S2) |
| W2 | Grade 1 has n=18/5 | No Grade-1 claim is statistically possible on IDRiD | MMRDR-CFP has 1,302 mild images (S1, S4) |
| W3 | Fixed 0.5 seg threshold, Dice-only | Field standard on IDRiD is AUPR (IDRiD challenge), so we are not comparable to literature | Add AUPR + val-tuned threshold (S6) |
| W4 | Patch sampling 50% lesion-centred | Inflates positive prior at training → FP explosion at inference. This is a *sampling/calibration* confound, not proof that "context is needed" | Matched-prior sampling + hard-negative mining (S6) |
| W5 | No clinically standard binary endpoint | Screening programmes are judged on *referable DR* sensitivity/specificity (grade ≥2), not 5-class macro-F1 | Add referable / vision-threatening endpoints (S2) |
| W6 | ECE 0.21–0.25 | Confidence display would mislead | Temperature scaling + selective prediction (S8) |
| W7 | No external data | Generalisation is fully unknown | Messidor-2 locked external (S1, S14) |
| W8 | Patient independence unknown (IDRiD and MMRDR-CFP) | Image-level splits may be optimistic | Disclose; Messidor-2 external test partly mitigates |
| W9 | Seg/grading cross-task links: only 3 exact | Cannot attribute grading errors to lesions on IDRiD | Do lesion-aware grading on MMRDR (image-level lesion labels) instead (S4) |
| W10 | No quality/gradability data | Problem says "real-world applicability"; ungradable images will be uploaded | Proxy QC + OOD gate, honestly labelled (S7) |

## 4. Should RETFound become the primary grading research direction?

**It should be the primary *candidate*, not the primary *decision*.** The research direction should be framed as a **controlled comparison of retinal-domain vs ImageNet pretraining**, with these arms:

| Arm | Backbone | Pretraining | Why included |
|---|---|---|---|
| A | ConvNeXt-Tiny | ImageNet-1k (supervised) | Current baseline, re-trained with an adequate budget |
| B | RETFound-MAE CFP ("natureCFP") | MAE on ImageNet-1k → 904,170 CFP (815,468 MEH-MIDAS + 88,702 Kaggle EyePACS) [P] | Hypothesis under test |
| C | RETFound-DINOv2 (if CFP-specific weights confirmed) | DINOv2 on retinal data | [P] generalist-vs-specialist preprint (arXiv:2509.03421) reports RETFound-DINOv2 > MAE and > generalist DINOv2/v3. Preprint, not peer-reviewed |
| D (SHOULD) | RETFound-Green, ViT-S | 75k public retinal images | Deployability on CPU; preprint claims parity [P, preprint] |
| E (OPTIONAL) | DINOv2 ViT-B generalist | Natural images (self-supervised) | Separates "SSL" from "retinal domain" |

Key rules:
- **Same splits, same input size (224 native for RETFound; ConvNeXt also at 224), same head, same epochs/early stopping, same seeds.** We will also report ConvNeXt at its best resolution as a separate row.
- **Use only pretrained-only weights.** The RETFound repo also releases checkpoints *fine-tuned* on public sets, including IDRiD. Those used IDRiD's official split, which overlaps our clean test through the duplicate leakage we found. Using them would contaminate the test.
- **CFP weights only.** Never use OCT weights for fundus.
- The RETFound weights are **gated on Hugging Face**. A team member must request access personally.

**Decision rule (pre-registered here):** RETFound replaces ConvNeXt only if, in the IDRiD 3-fold × ≥3-seed comparison, it improves QWK **and** does not worsen severe under-grading (grade 3/4 predicted as 0/1). The improvement must exceed seed spread (paired bootstrap 95% CI excluding 0). Otherwise ConvNeXt stays, and we report RETFound honestly.

## 5. Should MMRDR-CFP be downloaded and audited next?

**Yes, with corrections to our assumptions.**

Verified facts [P: Sci Data 13:639 (2026), DOI 10.1038/s41597-026-07005-9; figshare 10.6084/m9.figshare.29423747.v2]:
- **Counts:** 11,118 CFP, 10,404 UWF and 2,938 OCT, for 24,460 images in total.
- **CFP grade distribution:** No DR 6,579; Mild 1,302; Moderate 1,959; Severe 603; PDR 675.
- **CFP source:** OIA-DDR. Two junior ophthalmologists applied quality control. The paper does not say whether the DDR labels were re-graded. *Unresolved; we must compare against the original DDR labels if we obtain DDR.*
- **Split:** CFP is split at **image level** (no patient IDs in DDR); UWF and OCT at patient level. Ratio is about 8:2. Files are named `tr######.jpg` / `ts######.jpg`.
- **CFP lesion labels:** **image-level 7-way presence vector**, not masks and not boxes. The seven lesions are MA, hard exudate, intraretinal haemorrhage, **venous beading/IRMA, neovascularisation, vitreous haemorrhage, retinal detachment**.
- **Grading standard:** cites Wilkinson 2003 (ICDR) and ICO 2018, with the 4-2-1 rule for severe NPDR.
- **Annotators:** 4 senior ophthalmologists and 1 retinal specialist (Qingdao Eye Hospital). Calibration set of 130 images; κ ≥ 0.75 for CFP/UWF.
- **Licence:** CC BY 4.0.
- **Size:** 18.6 GB as a **9-part multi-volume zip**.

Corrections to our premises:
- **We cannot download "only CFP".** The archive is one split zip, so we need all 9 parts (18.6 GB). D: has 444 GB free, so this is fine. We **extract** only `MMRDR-CFP/`, and record that the other modalities are present in the archive but unused.
- **The lesion labels are a better fit than we assumed.** VB/IRMA and NV are exactly the signs that define severe NPDR and PDR beyond MA/HE/EX. They give a supervised route to "global pathology" that IDRiD masks cannot.
- **MMRDR-CFP does not prove patient-level generalisation**, and it is **not** independent of DDR.

## 6. Dataset roles (contract)

Each dataset gets fixed roles. A role change requires a decision-log entry *before* looking at results.

| Dataset | Role(s) | Never used for |
|---|---|---|
| RETFound pretraining corpus (MEH-MIDAS + EyePACS) | Representation pretraining (given) | — |
| **MMRDR-CFP `tr`** | Supervised adaptation (grading + 7-lesion presence); internal validation carved from `tr` after dedup | Final claims of generalisation |
| **MMRDR-CFP `ts`** | Internal test for the MMRDR-adapted model (image-level, same distribution). Looked at **once per locked candidate** | Model selection |
| **IDRiD clean train (404)** | In-domain adaptation + 3-fold CV model selection | — |
| **IDRiD clean test (102)** | Locked internal test, evaluated **once** after the full pipeline is locked (S14) | Anything before S14 |
| **IDRiD segmentation (81; official train/test)** | Pixel-level supervision (train split) + seg test (official test) | Grading test |
| DDR lesion-seg subset (757, MA/HE/EX/SE masks) — SHOULD | Extra segmentation training data | External test (shares lineage with MMRDR-CFP) |
| **Messidor-2** (adjudicated grades, ~1,748 images) | **Primary locked external test** (France, different cameras/population). Evaluated **once** | Any tuning, including threshold or temperature |
| APTOS-2019 train (3,662, India) — SHOULD | Secondary external test, "India-relevant", after its own duplicate audit | Training |
| EyePACS / EyeQ | **Not** an external test for RETFound (88,702 EyePACS images are in RETFound pretraining) | External evaluation |

Calibration and threshold data come from **validation folds**, never from a test set.

## 7. Contamination and lineage risks

1. **MMRDR-CFP ⊂ OIA-DDR.** Any DDR-derived set (DDR grading, DDR lesion-seg, OIA-DDR mirrors) is **in-distribution, possibly the same images**. It can never be external if MMRDR is used for training.
2. **Image-level splits inside MMRDR-CFP.** DDR has 13,673 images from 9,598 patients [P, via DDR repo/HF mirror], so ~1.4 images per patient on average. Fellow eyes and repeat images can straddle `tr`/`ts`. We will run exact-hash and perceptual-hash checks across `tr`/`ts` and report the count. We cannot detect fellow eyes.
3. **RETFound × EyePACS.** Unlabelled EyePACS images are in pretraining. This is not label leakage, but EyePACS-derived sets (EyeQ, Kaggle DR 2015) are not clean external tests for arm B.
4. **RETFound × IDRiD / APTOS / Messidor-2 fine-tuned checkpoints.** Never load those.
5. **APTOS and IDRiD are both Indian; IDRiD was collected in Nanded.** Patient overlap is unlikely but unprovable. Run cross-dataset hash checks anyway.
6. **Messidor-2 grade source.** Use one label source, recommended Krause et al. 2018 adjudicated grades [P?], and state which. Messidor-2 has very few PDR images [P?]; report per-grade counts before evaluation.
7. **Cross-dataset duplicates.** Public DR sets are re-hosted and mixed (Kaggle mirrors). Before any evaluation, run hash and pHash checks across **all** datasets we hold (IDRiD, MMRDR-CFP, Messidor-2, APTOS, DDR-seg).

## 8. Research questions (final)

| RQ | Question | Primary data | Primary metric | Min. evidence to claim |
|---|---|---|---|---|
| RQ1 | Does RETFound-CFP beat a properly trained ImageNet ConvNeXt on clean IDRiD? | IDRiD 3-fold × 3 seeds | QWK; macro-F1; referable-DR AUROC | Paired bootstrap CI excludes 0 |
| RQ2 | Does it improve mild-NPDR recall without hurting grade 3/4 recall? | **MMRDR-CFP** (IDRiD n too small) | Grade-1 recall; severe under-grading rate | CI on MMRDR `val` |
| RQ3 | Does MMRDR supervised adaptation → IDRiD beat direct → IDRiD? | IDRiD CV after MMRDR stage | QWK, macro-F1 | As RQ1 |
| RQ4 | How do we preserve MA without FP explosion? | IDRiD seg (+DDR-seg) | MA AUPR, component P/R | Fixed val set, ≥3 seeds |
| RQ5 | Does a lesion-presence auxiliary head improve grading? | MMRDR-CFP | QWK, grade-1 and grade-3/4 recall | Paired CI |
| RQ6 | Does the locked system hold under domain shift? | Messidor-2 (+APTOS) | Referable sens/spec, QWK | Single locked evaluation |
| RQ7 | Which errors are dangerous? | All test sets | Under-grading ≥2 grades; 3/4 → 0/1 | Report counts with CIs |
| RQ8 | Can uncertainty flag cases for review? | IDRiD/MMRDR val → test | Risk–coverage curve, ECE before/after | Lower error on accepted cases at fixed coverage |
| RQ9 | Do attributions land on pathology? | IDRiD seg test images | Pointing game / lesion-mass-in-map vs masks | Comparison vs random-map baseline |

## 9. Candidate system architecture (PROVISIONAL)

```
Upload (JPEG/PNG)
  → [Q] Image-quality / gradability gate (proxy metrics + OOD score)  → "Retake / clinician review" if fails
  → Retinal preprocessing (FOV mask, crop to disc, resize; no CLAHE unless validated)
  ├→ [G] Grader: backbone (ConvNeXt or RETFound; decided in S5)
  │       heads: 5-grade softmax (+ ordinal decoding)  +  7-lesion presence (MMRDR aux)  [if RQ5 positive]
  │       → temperature scaling → selective prediction / abstention
  │       → outputs: grade, P(referable DR ≥2), P(vision-threatening ≥3), lesion-presence probabilities
  ├→ [S] Segmentation: MA / HE / EX (/ SE) masks at ≥1024 px-width tiles, val-tuned thresholds
  └→ [X] Attribution: Grad-CAM (ConvNeXt) or ViT-appropriate method (chosen in S9) — labelled "classifier attention", not lesions
  → Evidence-consistency checks (e.g. grade ≥1 but zero lesions detected → flag)
  → Referral suggestion (screening language only) + structured report (PDF/JSON)
```

Principles:
- Grading and segmentation are **separate models**. There is no multi-task fusion unless RQ5 and S6 justify it.
- Lesion overlays and attribution maps are **displayed separately and labelled differently**.
- The output is a **screening/referral suggestion**: "Refer to ophthalmologist within X" follows a published referral scheme (ICO 2018 [P?]) and is shown as guidance requiring clinician confirmation. No diagnosis, no treatment.

## 10. Stage-by-stage research plan

| Stage | Name | Core question answered |
|---|---|---|
| S0 | Research consolidation (this doc, ledgers) | What do we believe, and on what evidence? |
| **S1** | **Data acquisition + MMRDR-CFP / Messidor-2 audit + cross-dataset lineage check** | Which datasets may play which role? |
| S2 | Evaluation harness + strong ConvNeXt baseline | What is the real baseline once under-training is removed? |
| S3 | RETFound on IDRiD (LP local; FT cloud) | RQ1 |
| S4 | MMRDR-CFP supervised adaptation + lesion-aux ablation | RQ2, RQ3, RQ5 |
| S5 | Grader lock | Which candidate ships? |
| S6 | Segmentation improvement (parallel track after S2) | RQ4 |
| S7 | Quality gate | What do we refuse to grade? |
| S8 | Calibration, uncertainty, abstention | RQ8 |
| S9 | Explainability + evidence consistency | RQ9 |
| S14 | Locked internal + external evaluation (once) | RQ6, RQ7 |

## 11. Stage-by-stage engineering plan

| Stage | Name | Starts after |
|---|---|---|
| S10 | Unified inference package (`src/inference/`), model registry, deterministic loading | S5 (can use the current baseline behind a fixed interface earlier) |
| S11 | FastAPI backend | S10 |
| S12 | Clinical frontend (React + Vite) | S11 schema frozen |
| S13 | Structured report (PDF + JSON) | S11 |
| S15 | Docker packaging, CPU path, latency optimisation | S14 |
| S16 | Judge pack: slides, demo script, failure cases, question bank | Continuous; final after S14 |

**Ordering note:** S14 (locked evaluation) runs **after** S5–S9 lock and **before** S15/S16. Engineering S10–S13 can proceed in parallel with research once S5 has fixed the model *interface*, by swapping weights rather than code.

## 12. Acceptance criteria per stage

**S1 — Data acquisition & audit**
- MMRDR archive: all 9 parts present; byte sizes match figshare; multi-part archive tests OK.
- Only `MMRDR-CFP/` extracted; raw folder read-only; SHA-256 manifest.
- Decode every image. Then report:
  - counts per split vs paper (11,118; per-grade counts)
  - corrupt files
  - resolution distribution
  - exact and perceptual duplicates within `tr`, within `ts`, and across `tr`/`ts`
  - label conflicts among duplicates
  - laterality distribution
  - lesion-label prevalence per grade, with a sanity matrix (e.g. NV present in grade <4 should be ~0)
- CSV schema documented (actual column names).
- Messidor-2 and adjudicated grades acquired (if licence accepted); same audit.
- **Cross-dataset** exact + pHash overlap matrix: IDRiD × MMRDR-CFP × Messidor-2 (× APTOS if acquired).
- Dataset role contract (§6) written as `docs/dataset_audit/DATASET_ROLES.md` and frozen.
- MMRDR internal validation carve-out from `tr` (stratified, hash-group-aware) frozen as a manifest.
- Reproducibility: regenerating manifests yields identical bytes.

**S2 — Harness + strong baseline**
- One metric library used by all arms, covering:
  - QWK, macro-F1, per-class recall with Wilson CIs, confusion matrix
  - referable-DR (≥2) sensitivity/specificity/AUROC
  - vision-threatening (≥3) sensitivity
  - severe under-grading count and rate
  - NLL, Brier, ECE (15-bin), paired bootstrap
- ConvNeXt-Tiny retrained with a **convergence-checked** budget: validation loss plateaus, early stopping on val QWK, ≥3 seeds, 3 folds, at 224 and 512.
- Report whether the 6-epoch conclusions survive. Unit tests cover the metric functions against hand-computed examples.

**S3 — RETFound on IDRiD**
- LP and FT for arm B (FT on cloud GPU, environment recorded), ≥3 seeds × 3 folds; same harness.
- Paired comparison vs S2 baseline with CIs; decision per §4 rule recorded in the decision log.

**S4 — MMRDR adaptation**
- Arms A and B (and C if available) trained on MMRDR `tr` and evaluated on the MMRDR `val` carve-out.
- Ablation: ± lesion-presence auxiliary head.
- Transfer to IDRiD CV vs direct. Grade-1 recall with CI from MMRDR `val` (n ≈ 200).
- MMRDR `ts` evaluated **once**, only for the locked S5 candidate.

**S5 — Grader lock**
- One frozen config + checkpoint hash.
- Claims ledger updated with every number we will present.

**S6 — Segmentation**
- Per-lesion AUPR (IDRiD challenge convention) + Dice at val-tuned threshold + component-level P/R for MA.
- ≥3 seeds; train ≥ convergence (not 6 epochs).
- Experiments: full image at 1024/1440 width with large random crops vs native-patch with **matched prior** sampling + hard-negative mining.
- Overlays for 10 fixed cases including the worst failures.
- Evaluation on IDRiD official seg test, once.

**S7 — Quality gate**
- Documented proxy checks: FOV detection, exposure, blur (variance of Laplacian on FOV), field coverage.
- Thresholds set on IDRiD/MMRDR train distribution, plus an OOD score from grader features.
- Tested on synthetic degradations and non-fundus images (non-fundus rejection ≥ 99% on a test set we assemble).
- UI wording: "image quality may be insufficient", never "clinically ungradable".

**S8 — Calibration**
- Temperature fitted on validation folds.
- ECE before/after; risk–coverage curve.
- Abstention threshold chosen on validation, reported on test once.

**S9 — Explainability**
- Method chosen by comparison on the IDRiD seg test (pointing game vs masks, vs random baseline).
- Sanity check (Adebayo et al. 2018 [P?] model-randomisation test) passed.
- Evidence-consistency rules documented and tested.

**S10–S13 — Inference / API / UI / report**
- Models load once at startup.
- Pydantic request/response schema, versioned; meaningful 4xx errors (bad type, too small, not fundus).
- `/health` and `/version` (model hashes).
- p95 latency measured on GPU and CPU.
- pytest coverage of the API contract.
- Frontend:
  - every number shown comes from the API (no placeholders)
  - loading and error states
  - colour-blind-safe overlays, toggleable per lesion
  - disclaimer always visible
- Report shows model version, quality status, grade + confidence category, lesion summary, referral suggestion, limitations.

**S14 — Locked evaluation**
- Pre-registered analysis plan committed *before* running.
- IDRiD clean test, MMRDR `ts`, Messidor-2 (and APTOS) each evaluated once; outputs hashed.
- No post-hoc changes; if something is wrong, it is reported, not re-run quietly.

**S15 — Deployment**
- `docker compose up` gives a working app from clean.
- CPU-only path documented with latency.
- Offline operation (no external calls).
- Images not persisted by default.

**S16 — Judge pack**
- Every slide number traced to a claims-ledger ID.
- Demo has a scripted happy path plus 3 failure cases: blurry image, non-fundus image, uncertain case.

## 13. Literature, ranked

| # | Source | Status | Why it matters |
|---|---|---|---|
| 1 | Zhou et al., *A foundation model for generalizable disease detection from retinal images*, Nature 622:156 (2023), doi:10.1038/s41586-023-06555-x | [P] read | RETFound: ViT-L, MAE (mask 0.75 CFP), 904,170 CFP; IDRiD AUROC 0.822; FT batch 16, 50 epochs, lr warmup to 5e-4 + cosine, label smoothing |
| 2 | Tang et al., *A multimodal retinal image dataset for DR detection using foundation models*, Sci Data 13:639 (2026), doi:10.1038/s41597-026-07005-9 | [P] read | MMRDR facts above; RETFound ≈ ResNet-50 on CFP |
| 3 | Porwal et al., IDRiD challenge, Medical Image Analysis (2020) | [P?] | Seg metric convention (AUPR) and reference scores. Our seg numbers are not comparable until we use AUPR |
| 4 | Li et al., DDR, Information Sciences 501:511 (2019), doi:10.1016/j.ins.2019.06.011 | [P] partial | MMRDR lineage; 13,673 images / 9,598 patients; 757 lesion-mask images |
| 5 | Krause et al., *Grader variability and the importance of reference standards…*, Ophthalmology (2018) | [P] abstract | Messidor-2 adjudicated labels; inter-grader κ 0.40–0.65 → why our labels are noisy |
| 6 | Wilkinson et al., ICDR scale, Ophthalmology (2003); Wong et al., ICO guidelines (2018) | [P?] | Grade definitions, 4-2-1 rule, referral timing |
| 7 | Gulshan et al., JAMA (2016); Abràmoff et al., npj Digit Med (2018, IDx-DR pivotal) | [P?] | Referable-DR endpoint, clinical reporting norms |
| 8 | Zhou et al., *Generalist versus specialist vision foundation models…*, arXiv:2509.03421 (2025) | [P] abstract | RETFound-DINOv2 > generalist DINOv2/v3; preprint |
| 9 | Engelmann et al., RETFound-Green, arXiv:2405.00117 | [P] secondary | Small ViT-S retinal FM; deployable |
| 10 | Cascone et al. (2026), XAI benchmark on DINOv2 DR ViT | [P] secondary | Grad-CAM best detection balance; rollout costly/diffuse; no single best |
| 11 | Barekatain & Glocker, arXiv:2510.12021 (2025) | [P] abstract | Grad-CAM on ViTs more faithful than gradient-rollout (non-retinal) |
| 12 | Adebayo et al., *Sanity Checks for Saliency Maps*, NeurIPS (2018) | [P?] | Mandatory attribution sanity test |
| 13 | Guo et al., *On Calibration of Modern Neural Networks*, ICML (2017); Angelopoulos & Bates, conformal prediction tutorial (2021) | [P?] | Temperature scaling; prediction sets |
| 14 | Fu et al., EyeQ quality dataset, MICCAI (2019) | [P?] | Quality grading; note: EyePACS-derived |

The existing `DR_MODEL_LITERATURE_REVIEW.md` (21 sources) remains valid. Add rows 1–2, 4, 5, 8–11 to `outputs/metrics/model_selection/literature_evidence.csv` in S2.

## 14. Experiments, ranked

**MUST**
1. S1 audits (MMRDR-CFP, Messidor-2, cross-dataset overlap).
2. S2 strong ConvNeXt baseline (convergence-checked, ≥3 seeds).
3. S3 RETFound-CFP LP + FT on IDRiD, paired with S2.
4. S4 MMRDR-CFP training for the best two arms; grade-1 recall with CI.
5. S6 MA: matched-prior patch vs high-res full-image crop, AUPR, val-tuned threshold.
6. S8 temperature scaling + abstention risk–coverage.
7. S14 locked IDRiD-test + Messidor-2 evaluation.

**SHOULD**
8. Lesion-presence auxiliary head ablation (RQ5).
9. RETFound-DINOv2 arm; RETFound-Green arm for CPU deployability.
10. DDR-seg as extra segmentation training (after overlap check).
11. Attribution vs mask agreement (RQ9).
12. APTOS secondary external with its own audit.

**OPTIONAL**
13. Generalist DINOv2 control arm.
14. LoRA vs full FT for RETFound.
15. Conformal prediction sets.
16. Test-time augmentation.

## 15. What NOT to spend time on

- OCT/UWF modalities, multimodal fusion, GNN fusion, vision-language models / generated-text reports.
- DME grading as a model output. IDRiD's DME labels are photographic exudate proximity, not OCT; mention it as future work.
- Training from scratch; architecture zoo searches; ensembles of 5 backbones.
- CLAHE/Ben-Graham preprocessing sweeps (unless S2 shows a clear failure they address).
- Microservices, Kubernetes, model servers (Triton), auth systems, databases of patients.
- Mobile apps, federated learning, blockchain.
- Tuning anything on Messidor-2 or the IDRiD clean test.

## 16. Major technical risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| ViT-L FT impossible on 4 GB | Certain locally | Kaggle/Colab 16 GB; LP locally; RETFound-Green fallback |
| Free cloud GPU quotas/time limits | High | Checkpoint every epoch; small epoch budgets with early stopping; record environment |
| RETFound HF access delayed | Medium | Request today; S2 doesn't need it |
| MMRDR CSV schema differs from paper | Medium | S1 documents actual schema before any training |
| Messidor-2 licence/form delay | Medium | Request in S1; APTOS as fallback external (noisier) |
| MA segmentation stays weak | High | Present as "candidate MA evidence" with recall/precision; don't hide it |
| Overfitting model selection to IDRiD CV with many arms | Medium | Pre-register arms; report all |

## 17. Major clinical risks

- **Missed PDR / severe NPDR** (under-grading). Track 3/4 → 0/1 explicitly. Any abstention must prefer referral.
- **Ungradable image graded confidently.** Quality gate + OOD + abstention.
- **Automation bias.** Heatmaps look authoritative. Label attribution as "where the model looked", not "lesions".
- **Population shift** (Indian rural cameras, handheld devices). We have no handheld-camera data; state this.
- **Misread as diagnosis/treatment.** Screening language and a persistent disclaimer.

## 18. Major hackathon risks

- Spending all remaining time on experiments with no working demo. **Engineering track must start by S5 at the latest.**
- Judges equating "RETFound" with novelty. It isn't novel; the controlled comparison and safety layer are the story.
- Overloaded slides. Lead with the 3 findings that changed our design.
- Demo failure on venue hardware. Offline Docker image + recorded backup video.
- The official hint says APTOS/Messidor + EfficientNet/ViT + Grad-CAM. Judges may ask why we deviated. Answer: we *use* Messidor-2 and APTOS for external evaluation, *compared* EfficientNet, and ViT is covered by RETFound.

## 19. Judge question bank

Maintained in `docs/judging/JUDGE_QUESTION_BANK.md`, with evidence pointers and current answer status.

## 20. Recommended prototype workflow (clinician view)

1. Upload a fundus image (or pick from a demo gallery of images *not* from any training set).
2. **Quality panel:** Pass / "Image quality may be insufficient — retake recommended", with reasons (blur, exposure, field).
3. **Result card:**
   - grade (ICDR name)
   - confidence category (High / Moderate / "Insufficient confidence — clinician review recommended")
   - P(referable DR)
4. **Evidence tabs:**
   - (a) Lesion map: MA/HE/EX toggles, counts and areas
   - (b) Lesion presence: from the aux head, if shipped
   - (c) Classifier attribution: labelled clearly
5. **Consistency notes:** e.g. "Grade suggests moderate NPDR; few lesions detected; review recommended."
6. **Screening suggestion:** e.g. "Referable DR suspected — refer to ophthalmologist", using ICO-based wording. Clinician can **override** the grade and add notes.
7. **Download report** (PDF/JSON), with model version, limitations and disclaimer.

## 21. Technology stack

| Layer | Choice | Reason |
|---|---|---|
| ML | PyTorch + timm + segmentation_models_pytorch (already in env: torch 2.11, timm 1.0.30, smp 0.6.0) | Continuity |
| Cloud training | Kaggle Notebooks or Colab (T4/P100 16 GB) | ViT-L FT needs >4 GB |
| Backend | FastAPI + Pydantic, single process, models loaded at startup | Simple; async upload handling |
| Frontend | React + Vite + TypeScript; Tailwind; canvas overlays | Fast to build; Next.js SSR unnecessary |
| Report | HTML template → PDF (WeasyPrint) or ReportLab | Offline |
| Packaging | Docker (CPU image + optional CUDA image), docker compose | Reproducible demo |
| Optimisation (S15) | ONNX Runtime CPU for ConvNeXt/SegFormer; fp16 on GPU | Rural / CPU story |

## 22. Deployment strategy

- **Demo:** laptop with RTX 3050 runs everything locally, fully offline. Also produce a CPU-only Docker image and measure its latency.
- **"Rural clinic" story:**
  - offline edge box or laptop
  - no internet required
  - images processed in memory and not stored unless the clinician saves a report
- **If RETFound ViT-L ships:** measure CPU latency honestly. If > ~10 s/image, offer RETFound-Green or ConvNeXt as the CPU tier and state the trade-off.
- **Do not** claim regulatory readiness, DPDP/HIPAA compliance, or clinical deployment.

## 23. Evidence to collect for PPT/demo

1. IDRiD audit: duplicate/conflict table, including the IDRiD_118 (grade 0) vs IDRiD_064 (grade 3) example.
2. Resolution → MA-component-loss curve.
3. "What failed" slide: 6-epoch screens, patch FP explosion, SegFormer MA=0, Grade-1 16.7% with its CI.
4. RETFound vs ConvNeXt paired comparison, with CIs, on IDRiD and MMRDR.
5. Grade-1 recall on MMRDR val, before/after.
6. Confusion matrices; severe under-grading counts.
7. Reliability diagram before/after temperature scaling; risk–coverage curve.
8. Segmentation AUPR per lesion vs IDRiD challenge reference (properly attributed), plus overlays including failures.
9. Attribution sanity check + pointing-game result.
10. Messidor-2 external results (single locked run).
11. Latency/size table (GPU, CPU).
12. Dataset-role diagram showing lineage (MMRDR ⊂ DDR; RETFound ⊃ EyePACS).

## 24. Genuine innovation (realistic)

1. **Integrity-first protocol:** a reproducible audit that found label-conflicting duplicates and cross-split leakage in IDRiD, and a lineage-aware dataset-role contract (MMRDR ⊂ DDR, RETFound ⊃ EyePACS). This is uncommon, verifiable and useful.
2. **A controlled answer to "does retinal foundation pretraining help small, clean DR datasets?"** Paired, multi-seed, with grade-level and dangerous-error analysis, not just accuracy.
3. **Severity-relevant lesion supervision.** If RQ5 is positive, image-level VB/IRMA/NV supervision addresses the gap that MA/HE/EX masks cannot explain severe NPDR/PDR.
4. **A safety layer:** quality gate + calibrated abstention + grade-vs-lesion evidence-consistency flags, presented as a screening workflow.

## 25. What we must NOT claim as innovation

- Using RETFound, ViT, ConvNeXt, SegFormer, U-Net, Grad-CAM, FastAPI or React.
- "Multi-task" or "global-local" models (well-established in the literature).
- "Explainable AI" from heatmaps alone.
- Clinical validation, diagnostic accuracy, regulatory readiness, patient-level generalisation, rural-deployment validity.
- Matching published SOTA numbers on different splits.

## 26. Next single stage

**S1 — Data acquisition, MMRDR-CFP + Messidor-2 audit, and cross-dataset lineage check.** See the GO/NO-GO below and in the chat summary.

### GO / NO-GO

**GO for S1**, conditional on three actions only the team can take:
1. Approve downloading the 18.6 GB MMRDR archive (9 parts, CC BY 4.0) into `D:\DR_Hackathon\data\raw\MMRDR\`.
2. Accept the Messidor-2 licence/terms on the official site yourselves, and obtain the Krause adjudicated grade CSV. If you can't, S1 proceeds with MMRDR only, and APTOS replaces Messidor-2 as a weaker external set.
3. Request RETFound access on Hugging Face now. It is not needed until S3, but there is a lead time.

**NO-GO for any modelling stage (S2+)** until S1's role contract is frozen.

**S1 objective:** establish what MMRDR-CFP (and Messidor-2) actually contain, whether they are clean, how they relate to IDRiD and to each other, and freeze each dataset's role before any model sees them.

**S1 acceptance criteria:** as listed in §12 under S1, plus no training and no model inference on any new dataset.

### Proposed directory additions (inside `D:\DR_Hackathon`)

```
data/raw/MMRDR/            # immutable: 9 zip parts + README + extracted MMRDR-CFP/ (read-only)
data/raw/Messidor2/        # immutable
data/raw/APTOS2019/        # optional, immutable
data/interim/manifests/    # existing; add mmrdr_cfp_*.csv, messidor2_*.csv, cross_dataset_overlap.csv
docs/dataset_audit/        # add MMRDR_CFP_AUDIT.md, MESSIDOR2_AUDIT.md, DATASET_ROLES.md
docs/research/             # this file, CLAIMS_LEDGER.md, ARCHITECTURE_DECISION_LOG.md
docs/judging/              # JUDGE_QUESTION_BANK.md
configs/experiments/       # existing
configs/inference/         # S10: locked model config
src/data/                  # add audit_mmrdr.py, audit_messidor2.py, cross_dataset_overlap.py
src/evaluation/            # S2: shared metric library
src/research/              # S2–S6 experiment runners (successor to src/model_selection)
src/inference/             # S10
backend/                   # S11 FastAPI app
frontend/                  # S12 React app
reports/                   # S13 templates + generated samples
deploy/                    # S15 Dockerfiles, compose
models/registry/           # locked checkpoints + hashes
```
