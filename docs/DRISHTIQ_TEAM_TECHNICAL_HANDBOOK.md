# DrishtiQ — Team Technical Handbook

**Who this is for:** every teammate, including those who did not train the models. Read it start to finish once; after that, use the
[cheat sheet](DRISHTIQ_TEAM_CHEAT_SHEET.md) and the [judge viva](DRISHTIQ_JUDGE_VIVA.md).

**How to read it:** hard ideas are explained three times: **Simple** (one or two sentences), **Technical** (accurate detail) and
**Why it matters in DrishtiQ**. Every important number names the file it comes from. If a number could not be traced to the
repository it says **NOT VERIFIED FROM REPOSITORY**.

**The four labels used everywhere**

| Label | Meaning |
|---|---|
| **[IMPLEMENTED]** | Exists and runs in the frozen application (tag `rc-1`, commit `564c7b7`) or, where stated, in the UI branch `ui-v3`. |
| **[EXPERIMENT]** | Tested in a research experiment; not necessarily part of the app. |
| **[PROPOSED]** | An idea we think is worth testing. Not built, not validated. |
| **[REJECTED]** | Tested or argued, and the evidence does not support it. |

**What "frozen" means here:** the system was frozen as release candidate `rc-1` (git tag on commit `564c7b7`, decision log ADR-045)
before the locked tests were run. The warm "DrishtiQ" interface and landing page live on branch `ui-v3`; they change the look, not
the models, thresholds or routing. The repository and some files still use the earlier working name **RetinaScreen**.

---

## Contents

- [Part 1 — DrishtiQ in 30 seconds](#part-1--drishtiq-in-30-seconds)
- [Part 2 — The medical problem from zero](#part-2--the-medical-problem-from-zero)
- [Part 3 — The real-world problem](#part-3--the-real-world-problem)
- [Part 4 — The user workflow, screen by screen](#part-4--the-user-workflow-screen-by-screen)
- [Part 5 — The pipeline in simple language](#part-5--the-pipeline-in-simple-language)
- [Part 6 — The dataset story](#part-6--the-dataset-story)
- [Part 7 — The IDRiD data-integrity story](#part-7--the-idrid-data-integrity-story)
- [Part 8 — Why resolution matters](#part-8--why-resolution-matters)
- [Parts 9–10 — Model evolution and the early baseline](#parts-910--model-evolution-and-the-early-baseline)
- [Part 11 — The active ConvNeXt-Tiny grader](#part-11--the-active-convnext-tiny-grader)
- [Part 12 — Why regression instead of five-class softmax](#part-12--why-regression-instead-of-five-class-softmax)
- [Part 13 — Exact preprocessing](#part-13--exact-preprocessing)
- [Part 14 — Active training data](#part-14--active-training-data)
- [Part 15 — Exact training parameters](#part-15--exact-training-parameters)
- [Part 16 — Why ConvNeXt-Tiny?](#part-16--why-convnext-tiny)
- [Part 17 — The RETFound experiment](#part-17--the-retfound-experiment)
- [Part 18 — Model size comparison](#part-18--model-size-comparison)
- [Part 19 — Development grading results](#part-19--development-grading-results)
- [Part 20 — Every metric explained for beginners](#part-20--every-metric-explained-for-beginners)
- [Part 21 — The Grade-1 problem](#part-21--the-grade-1-problem)
- [Part 22 — The Grade-4 / PDR problem](#part-22--the-grade-4--pdr-problem)
- [Parts 23–24 — Segmentation pipeline and results](#parts-2324--segmentation-pipeline-and-results)
- [Part 25 — Why microaneurysms are hard](#part-25--why-microaneurysms-are-hard)
- [Part 26 — The global + local idea (proposed)](#part-26--the-global--local-idea-proposed)
- [Part 27 — Quality and gradability](#part-27--quality-and-gradability)
- [Part 28 — Grad-CAM](#part-28--grad-cam)
- [Part 29 — Calibration and uncertainty](#part-29--calibration-and-uncertainty)
- [Part 30 — The locked IDRiD test](#part-30--the-locked-idrid-test)
- [Part 31 — DeepDRiD](#part-31--deepdrid)
- [Part 32 — Dataset lineage](#part-32--dataset-lineage)
- [Part 33 — Lesion counts](#part-33--lesion-counts)
- [Part 34 — Rural-first design thinking](#part-34--rural-first-design-thinking)
- [Part 35 — What makes DrishtiQ different](#part-35--what-makes-drishtiq-different)
- [Part 36 — What we must never claim](#part-36--what-we-must-never-claim)
- [Part 37 — What is missing for a real clinical system](#part-37--what-is-missing-for-a-real-clinical-system)
- [Part 38 — Future clinical-grade architecture (proposed)](#part-38--future-clinical-grade-architecture-proposed)
- [Part 39 — Complete scorecard](#part-39--complete-scorecard)
- [Part 40 — Complete model inventory](#part-40--complete-model-inventory)
- [Part 41 — Complete dataset inventory](#part-41--complete-dataset-inventory)
- [Part 42 — Complete experiment timeline](#part-42--complete-experiment-timeline)
- [Documentation conflicts found](#documentation-conflicts-found-while-writing-this-handbook)
- [Verification table — 30 key claims](#verification-table--30-key-claims)
- [The 15 things every DrishtiQ team member must know](#the-15-things-every-drishtiq-team-member-must-know)

The judge questions are in [DRISHTIQ_JUDGE_VIVA.md](DRISHTIQ_JUDGE_VIVA.md); the two-page summary is in [DRISHTIQ_TEAM_CHEAT_SHEET.md](DRISHTIQ_TEAM_CHEAT_SHEET.md).

---

## Part 1 — DrishtiQ in 30 seconds

**What is DrishtiQ?** A computer program that looks at a photograph of the back of the eye (a *fundus photograph*) of a person with
diabetes and helps a health team decide who needs an eye specialist first.

**Who uses it?** A health worker or technician who takes the photo, and a clinician (doctor or trained grader) who reviews the result.

**What goes in?** One colour fundus photograph per eye, a patient reference ID, which eye it is, and two optional questions (does the
patient report vision problems; has the eye been treated or lasered before).

**What comes out?**
- a photo-quality check (retake the photo, or go ahead);
- a suggested diabetic-retinopathy (DR) stage from 0 to 4;
- coloured maps of four kinds of small damage (lesions);
- a heatmap of where the grading model "looked";
- a calibrated chance that the eye needs a specialist, and a confidence;
- a worklist that puts the most urgent patients first, plus a doctor report and a patient summary (English or Hindi).

**Why is it useful?** In screening, the scarce resource is the specialist's time. Sorting cases so the urgent ones are seen first,
and catching bad photos while the patient is still there, uses that time better.

**What does it NOT do?** It does not diagnose. It does not replace the ophthalmologist. It does not decide on its own that a patient
can safely skip a specialist; our locked test rejected that claim (Part 30). It is a research prototype, not a medical device.

**30-second pitch**

> DrishtiQ is AI-assisted diabetic-retinopathy screening and clinical decision support. A health worker uploads a retinal photo; we
> check its quality, suggest a severity stage, mark lesions, and put the patient on a worklist ordered by urgency so the eye
> specialist sees the riskiest cases first. We built it data-integrity-first: we removed duplicate and contradictory labels, chose
> models by rules written before the results, and froze the system before testing it once on locked data, including a negative
> result we report openly. The ophthalmologist remains the final authority.

---

## Part 2 — The medical problem from zero

**The retina.** *Simple:* the light-sensitive layer at the back of the eye, like the film in a camera. *Technical:* a thin neural
tissue lining the inner back wall of the eye, supplied by small blood vessels that spread out from the optic disc.

**Fundus photograph.** A colour photo of the retina taken through the pupil with a special camera. It shows the optic disc, the
blood vessels, the macula and any visible damage. DrishtiQ only reads this kind of photo.

**Diabetes and retinal vessels.** Long-term high blood sugar damages the walls of small blood vessels. In the retina this makes
vessels leak, bulge, bleed or close off. That damage is **diabetic retinopathy (DR)**.

**Why patients often don't notice.** Early damage is scattered and usually away from the centre of vision, so sight feels fine
until the disease is advanced or the centre (macula) is affected. That is why people with diabetes need regular *screening*: a
photo check even when they see well.

**Why screening matters.** Advanced DR can cause permanent vision loss, but treatment (laser, injections, surgery) works best when
given in time. Screening finds the people who need treatment before they lose sight.

**The lesions (signs of damage)**

| Sign | Simple meaning | What it looks like | In DrishtiQ |
|---|---|---|---|
| Microaneurysm (MA) | a tiny bulge in a capillary wall | very small red dot, a few pixels at our grader's resolution | segmented (U-Net) [IMPLEMENTED] |
| Haemorrhage (HE) | small bleed inside the retina | red dot or blot, larger than MA | segmented (SegFormer) [IMPLEMENTED] |
| Hard exudate (EX) | leaked fat/protein deposits | bright yellow spots, sharp edges | segmented (SegFormer) [IMPLEMENTED] |
| Soft exudate / cotton-wool spot (SE) | swollen nerve fibres from blocked capillaries | fluffy pale-white patches | segmented (SegFormer) [IMPLEMENTED] |
| Venous beading | veins look like a string of beads | irregular vein calibre | **not detected** by any model |
| IRMA (intraretinal microvascular abnormality) | abnormal shunt vessels inside the retina | small tortuous vessels | **not detected** |
| Neovascularisation (NV) | fragile new vessels growing (the body's bad repair attempt) | fine vessel tufts on the disc or elsewhere | **not detected** |
| Vitreous / preretinal haemorrhage | bleeding into the gel in front of the retina | large dark area, can hide the retina | **not detected** |

**Landmarks.** The **optic disc** is where the nerve and vessels enter (the bright round spot). The **macula** is the central area
responsible for detailed vision; its centre is the **fovea**. DrishtiQ locates both with image heuristics [IMPLEMENTED; not validated
as a clinical tool].

**DME (diabetic macular edema).** Swelling of the macula from leaking vessels. It can threaten central vision at *any* DR stage,
which is why DME and DR stage are related but not the same thing: a stage-2 eye can have DME, a stage-4 eye may not. A photograph
cannot measure swelling (that needs OCT); it can only show *signs* such as hard exudates near the fovea. DrishtiQ's "swelling risk
at the centre of vision" is a **photographic proxy**: hard exudate within one disc diameter of the fovea (`configs/landmarks/dme_rule_v1.json`).

**The DR stages (ICDR scale)**

| Stage | Name | Simple description |
|---|---|---|
| 0 | No apparent DR | no visible DR signs |
| 1 | Mild NPDR | microaneurysms only |
| 2 | Moderate NPDR | more than microaneurysms, less than severe |
| 3 | Severe NPDR | widespread damage (the 4-2-1 rule below), no new vessels |
| 4 | Proliferative DR (PDR) | new vessels and/or vitreous/preretinal bleeding |

NPDR = non-proliferative DR. "Referable DR" in this project means **stage ≥ 2** (ADR-039).

**The 4-2-1 rule (severe NPDR), intuitively.** Severe NPDR means *any one* of: more than 20 haemorrhages in **each of 4** quadrants;
definite venous beading in **2 or more** quadrants; or prominent IRMA in **1 or more** quadrant. (This wording is in the docstring of
`src/inference/explanations.py`, citing Wilkinson et al., Ophthalmology 2003.)

**Why stage 4 cannot be found by counting MA/HE/EX.** Stage 4 is defined by *new vessels* or *vitreous/preretinal bleeding*, not by
how many dots there are. An eye can have few dots and still have new vessels on the disc. Our lesion models only know MA, HE, EX and
SE, so **no lesion count can prove or rule out PDR**. Even stage 3 depends partly on venous beading and IRMA, which we cannot segment.

**Why our lesion vocabulary cannot fully explain advanced DR.** Four lesion types cover mild and moderate disease reasonably, but the
defining signs of severe and proliferative disease (beading, IRMA, NV, vitreous haemorrhage) are outside the vocabulary. The grader
may still learn some of these patterns from whole images, but we cannot show them as lesion maps.

---

## Part 3 — The real-world problem

Not "classify images". The real workflow is:

```
PATIENT → retinal photograph → image-quality check → retinal analysis → specialist interpretation → referral / action
```

**Why this is hard in rural and underserved settings**
- **Few specialists:** the people who can interpret the photos are scarce and far away.
- **Variable operators:** the person taking the photo may be new to it.
- **Variable images:** different cameras, lighting, pupil size, patient cooperation.
- **Poor photos:** a blurred or dark photo discovered *after* the patient has left often means the patient is never re-photographed.
- **Travel and cost:** recalling a patient for a retake or a referral costs them time, wages and transport.
- **Specialist workload and delay:** when results arrive as an unsorted pile, urgent cases wait behind clear-looking ones.

**Our core systems insight.** The scarce resource is not computing power; it is **qualified specialist attention**. So DrishtiQ tries
to *organise* that attention: catch retakes early, put the riskiest eyes first, explain why, and leave every decision to the
clinician. It does not pretend to replace the specialist.

---

## Part 4 — The user workflow, screen by screen

```
Landing page (ui-v3) → New screening → patient ID + optional intake → right/left eye photos → quality check →
AI analysis (stage, lesions, Grad-CAM, calibrated confidence, routing) → results step (retake reasons) →
Worklist (ordered by urgency) → Case view (Simple / Clinical) → clinician review → Report (doctor; patient EN/HI)
```

| Screen | What the user sees | What happens inside | Model/component | Decision supported | Important limitation |
|---|---|---|---|---|---|
| Landing page [IMPLEMENTED on `ui-v3` only] | product overview, sourced statistics, "Start screening" | static page; reads `locked_results.json` for numbers | none | none | marketing page; the image of a screening camp is an illustration, labelled as such |
| New screening | patient ID, two optional intake boxes, right/left upload cards (or one slot if eye not recorded), image guidelines | each photo is posted to `POST /api/cases` | full pipeline per eye | which photo to analyse | intake answers only escalate; they never lower urgency |
| Results step (ui-v3) | per eye: stage or "Retake recommended" with the reasons in plain words; patient state | reads the analysis returned by the API | quality check + routing | retake now, before the patient leaves | the quality check is a heuristic, not a validated gradability model (Part 27) |
| Camp batch upload | many files at once, one case per file | same API in a loop | same | throughput | eye side often unknown, so routine routing is impossible without both eyes |
| Worklist | stat cards; tabs *Needs review / Routine rescreening / Reviewed / All*; rows with routing pill, stage, P(referable), confidence | sorted by routing state then P(referable) | routing (`src/inference/routing.py`) | who to look at first | the "routine" tab lists eligible **eyes**, so a routine eye of a patient whose other eye is urgent appears there too |
| Case view — viewer | dark image viewer, lesion overlay chips, "Where the AI looked", centre of vision, optic nerve head, Physician view (side by side), layer thumbnails | overlays are PNG masks from the segmenters and the Grad-CAM map | SegFormer-B0, MA U-Net, Grad-CAM, landmark heuristics | where to look on the image | overlays are model outputs, not confirmed lesions |
| Case view — stage card | Stage X, plain name, confidence badge, chance it needs a specialist, confidence in this stage, swelling risk | regression score → stage; Platt P(referable); isotonic stage confidence | ConvNeXt-T + calibration | how serious the AI thinks it is | confidence is not correctness (Part 29) |
| Case view — routing card | eye state with every reason, previous signed visit, intake | `routing.eye_state` | routing rules (ADR-040) | where the eye belongs in the queue | routine routing failed its locked test (Part 30) |
| Simple vs Clinical view | same facts in plain words or ICDR wording with exact values | same data, two text renderings | glossary + template explanations | understanding | explanations are templates built only from measured findings; they inherit the models' errors |
| Findings / Explanation | lesion counts and quadrants; macular box; sentences grouped (Summary, Evidence, Why this stage, Centre of vision, Limits, Checks); clicking a sentence highlights its lesions | `src/inference/explanations.py` (no language model) | findings record | why the AI suggests this | counts are connected regions in a model mask, not confirmed lesions (Part 33) |
| Review | Confirm stage / Change stage / Ungradable, reviewer name, optional DME and note | `POST /api/cases/{id}/review` stores a row | none | the clinician's decision | see the propagation note below |
| Report | doctor report (English) and patient summary (English or Hindi), print or PDF | server-rendered HTML (`backend/templates/report.html`), PDF via headless Edge | none | communication | Hindi wording is fixed text that has **not** been reviewed by a native-speaking clinician |
| Patient level | both eyes combined; the worse eye decides; a missing eye gives "incomplete screening" | `routing.patient_state` | routing | follow-up for the person, not the photo | patient-level routing has only been tested on DeepDRiD (Part 31) |

**Clinician correction does NOT fully propagate (verified in `backend/app.py`).** When a clinician confirms or changes a stage, the
review is stored, the case moves to the *Reviewed* tab, and the doctor report prints the review line ("Clinician review: disagree,
stage 2 …"). **But** the routing state of that same visit, the patient-level follow-up and the patient summary are still computed from
the **AI** stage. A signed referral only affects **later** visits of that eye (it stops them being routed to routine, function
`signed_referral` / `eye_routing`). Say exactly this if asked; do not claim the report follows the doctor's correction.

---

## Part 5 — The pipeline in simple language

```
FUNDUS IMAGE (any size, JPEG/PNG/TIFF/BMP)
      ↓
IMAGE PREPARATION   EXIF orientation, RGB
      ↓
QUALITY CHECK       field of view, corner darkness, colour, brightness, sharpness      → "retake" if it fails
      ↓
┌──────────────────────────────┐
│  DR SEVERITY GRADER           │   FOV crop → square → 384×384 → ConvNeXt-Tiny → ONE number (severity score)
│  ConvNeXt-Tiny (regression)   │
└──────────────────────────────┘
      ↓
Stage 0–4  (score compared with four cut points)
```

Separately, on the same photo:

```
FUNDUS IMAGE → letterbox 512×512 → LESION MODELS (SegFormer-B0 for HE/EX/SE; U-Net/ResNet18 for MA)
             → post-processing thresholds (pp_v2) → MA / HE / EX / SE masks → coloured overlays + counts per quadrant
```

and:

```
GRADER → Grad-CAM on its last stage → heatmap "where the grading model looked"
```

Then:

```
outputs (stage, score, quality, lesions, landmarks, macular proxy)
      ↓
calibration (P(referable), stage confidence) + routing rules (ADR-040)
      ↓
doctor worklist (urgent first) → clinician review → report
```

**Grad-CAM ≠ lesion segmentation.**
- *Grad-CAM* answers, approximately: "which image regions pushed the grader's score?" It is an attribution of **one** model.
- *Segmentation* answers: "which pixels does a **separate** lesion model think are lesion X?"
- *Expert mask*: what a human annotator marked. This is the reference, and we only have it for training/validation images.

**The lesion masks do not feed the grader.** The ConvNeXt grader sees only the 384×384 image. The lesion models run in parallel. So
never say "the stage was computed from the lesions". A lesion-to-grade fusion (ADR-021) was planned but **not run** (cancelled).

---

## Part 6 — The dataset story

| Dataset | Country / source | Images (as audited) | Resolution | Labels | Role in DrishtiQ | Split used | Main limitations |
|---|---|---|---|---|---|---|---|
| **IDRiD** | India (DATA_CARD) | 516 grading files (413 train + 103 test); 81 segmentation images | 4288 × 2848 | ICDR 0–4, DME risk 0–2; pixel masks MA/HE/EX/SE (+ OD); OD/fovea centres | grading train + validation + **locked internal test**; segmentation train/val | dev-train 303, val 101, clean test 102 | small; one clinic/camera; no patient IDs; duplicates with conflicting labels (Part 7) |
| **APTOS 2019** | India, Aravind Eye Hospital (DATA_CARD acknowledgements) | 3,662 train images | 17 distinct sizes, e.g. 1050², 2416×1736 | ICDR 0–4, one grader | grading training + validation | train 2,929, val 518 (3,447 kept) | one grader per image, label noise near boundaries; 123 exact-duplicate groups, 47 conflicting groups |
| **MMRDR (colour fundus subset)** | China (DATA_CARD: "MMRDR adds Chinese data") | 11,118 CFP | 1,857 distinct sizes, e.g. ~1659² | ICDR 0–4; image-level 7-way lesion presence | grading training only | 10,831 kept | derived from OIA-DDR (lineage, Part 32); image-level splits, no patient IDs |
| **DDR (OIA-DDR) lesion set** | NOT VERIFIED FROM REPOSITORY (country not recorded) | 757 lesion-segmentation images (383 train / 149 valid / 225 test) | e.g. 2592×1728 | pixel masks MA/HE/EX/SE (all four annotated per image) | segmentation evaluation (DDR-test 225) and planned A3 training (cancelled) | — | 647 of 757 are near-copies of MMRDR images |
| **DeepDRiD (regular fundus)** | NOT VERIFIED FROM REPOSITORY (country not recorded) | 2,000 images, 500 patients | — | ICDR grade per eye, "overall quality" | **locked external test** (run once) | 1,988 after leak removal; 1,977 gradable | 2 views per eye (correlated); 12 images removed as near-copies of training data |
| **EyePACS 2015** | — | not downloaded | — | — | planned conditional experiment (ADR-037), cancelled | — | in RETFound's pretraining |
| **Messidor-2** | — | not available on this machine | — | adjudicated grades | planned locked external test | — | **not evaluated** |

Sources: `results/audit/aptos/aptos_audit.json`, `results/audit/mmrdr/mmrdr_cfp_audit.json`, `results/audit/mmrdr/mmrdr_train_manifest_summary.json`,
`results/audit/ddr/ddr_seg_audit.json`, `results/audit/deepdrid/audit_summary.json`, `docs/dataset_audit/IDRiD_DATASET_AUDIT.md`, `docs/DATA_CARD.md`.

**In beginner language**
- **IDRiD:** a small, high-quality Indian dataset with expert grades and lesion drawings. Too small to train on alone, but the most
  careful labels we have. We use it to validate, and we locked part of it away as a final test.
- **APTOS:** a few thousand Indian photos from a Kaggle competition, each graded by one person. More data, more noise.
- **MMRDR:** about eleven thousand photos (Chinese), giving the grader many more examples of every stage, especially mild disease.
- **DDR:** photos with lesion drawings. Its images largely overlap MMRDR, which matters for what we can call "independent" (Part 32).
- **DeepDRiD:** a dataset we never trained or tuned on, with two photos per eye and quality labels. Our external test.

**Per-grade counts of the splits we use** (computed from `configs/splits/*.csv` and the clean manifests):

| Split | n | G0 | G1 | G2 | G3 | G4 |
|---|---|---|---|---|---|---|
| IDRiD dev-train | 303 | 100 | 13 | 99 | 55 | 36 |
| IDRiD-val | 101 | 33 | 5 | 33 | 18 | 12 |
| IDRiD clean test (locked) | 102 | 34 | 5 | 32 | 18 | 13 |
| APTOS-train | 2,929 | 1,507 | 283 | 778 | 140 | 221 |
| APTOS-val | 518 | 267 | 50 | 137 | 25 | 39 |
| MMRDR-train | 10,831 | 6,359 | 1,280 | 1,926 | 598 | 668 |
| DeepDRiD locked (graded images) | 1,977 | 903* | 218* | 393* | 351* | 112* |

\*DeepDRiD counts are from the full 2,000-image audit (`audit_summary.json`); 11 images are grade "None" (DeepDRiD's "cannot be graded")
and 12 were removed for leaks, so the locked per-grade counts differ slightly.

---

## Part 7 — The IDRiD data-integrity story

**[IMPLEMENTED in the data pipeline]** — sources: `docs/dataset_audit/IDRiD_DATASET_AUDIT.md`, `IDRiD_EXPERIMENT_POLICY.md`,
`IDRiD_LIMITATIONS.md`, `docs/research/CLAIMS_LEDGER.md` (C01–C03).

| Fact | Value | Verified |
|---|---|---|
| Grading records | 516 (413 official train + 103 official test) | ✓ audit |
| Distinct photographs | 510 (by SHA-256 of decoded pixels) | ✓ policy table "unique_contents" |
| Exact-duplicate groups | 6 | ✓ policy table (A_official_unchanged: 6 remaining groups) |
| Groups with conflicting DR/DME labels | 4 | ✓ CLAIMS_LEDGER C02, LIMITATIONS table |
| Cross-split duplicate | 1 (same image: IDRiD_118 train grade 0, IDRiD_064 test grade 3) | ✓ LIMITATIONS |
| Quarantined (all members of conflicting groups) | 8 (7 train, 1 test) | ✓ policy |
| Redundant agreeing duplicates dropped | 2 | ✓ policy |
| **Clean split** | **404 train / 102 test / 10 excluded = 506 distinct** | ✓ policy table PRIMARY_C_plus_D |
| Inside the 404: dev-train / val | 303 / 101 | ✓ splits |

**Why duplicates matter.** *Simple:* if the same photo is in both the study material and the exam, a good score proves memory, not
skill. *Technical:* an image in train and test inflates test metrics because the model has effectively seen it.

**Why conflicting labels matter.** The same photograph cannot be both grade 0 and grade 3. Training on both teaches the model a
contradiction; testing on one of them makes the "truth" arbitrary.

**Why we did not correct labels ourselves.** We are not the graders. Choosing which label is right would be inventing medical ground
truth. We quarantined the whole conflicting group instead and wrote the rule down (ADR-001).

**Patient-level independence — the limit.** IDRiD publishes no patient or eye IDs. Removing *exact* image duplicates does not rule out
two different photos of the same patient (fellow eye, repeat visit) on both sides of the split. **Exact-image leakage removed ≠
patient-level leakage ruled out.** We say "image-level clean split; patient independence cannot be verified".

**Missing segmentation masks.** Not every IDRiD image has every lesion mask (e.g. SE has 40 masks vs 81 images). A missing mask means
"not annotated", not "lesion absent". Our segmentation evaluation omits unavailable channels instead of counting them as negatives
(`configs/experiments/seg_*`: "unavailable channels omitted").

The same discipline was applied to the other sets: APTOS dropped 109 redundant duplicates, 98 images in conflicting groups and 8 that
match IDRiD images; MMRDR dropped 179, 62 and 46 near-copies of validation/locked images; DeepDRiD removed 12 near-copies of training
images. The hash is a calibrated 256-bit structure hash (duplicate ≤ 32, leak ≤ 42; `results/audit/hash_calibration.json`, DATA_CARD).

---

## Part 8 — Why resolution matters

**Simple.** Shrinking a large photo to a small square blurs tiny dots away. A model cannot see what is no longer in the picture.

**Technical evidence 1 — the whole IDRiD segmentation set** (`docs/dataset_audit/IDRiD_RESOLUTION_FINDINGS.md`, nearest-neighbour
sampling of the MA masks, 3,497 annotated MA components):

| Target width | MA components that disappear |
|---|---|
| 224 | 1,240 of 3,497 (35.5%) |
| 384 | 197 (5.6%) |
| 512 | 47 (1.3%) |
| 1024 | 2 (0.06%) |

**Technical evidence 2 — one image, IDRiD_21** (computed for this handbook, read-only, with the app's own `fov_box` geometry from
`src/inference/preprocess.py`; not a stored artifact):
- native size 4288 × 2848;
- retinal field-of-view crop 3410 × 2848, padded to a 3410 px square, resized to 384 px;
- so **one grader pixel covers about 8.9 × 8.9 native pixels** (scale 0.1126);
- **80** annotated microaneurysm components (8-connected) in `IDRiD_21_MA.tif`;
- native MA area: median 225 px (range 27–981);
- projected area at 384 px: **median 2.85 grader pixels**; **7 of 80** project to less than one pixel.

**What this proves and what it does not.** It is **geometric evidence of an information bottleneck**: at 384 px many microaneurysms
occupy only a few pixels and some less than one. It is **not proof** that resizing caused any particular classification error. That
would need a controlled experiment.

**Why a network cannot recover destroyed information.** Resizing averages neighbouring pixels. Once a 15-pixel dot is averaged into
its surroundings, the output image no longer contains it; no amount of training adds it back.

**Why DrishtiQ still uses 384.** Feasibility. The prior screen (6-epoch budget) found larger inputs did not justify their cost
(`STUDY_EXECUTION_SUMMARY.md`), and in the A2 screen 512 px gave no inner-hold-out gain (0.928 vs 0.929) at 1.8× the training time
(ADR-015). The bottleneck is real; 384 was a compute trade-off.

---

## Parts 9–10 — Model evolution and the early baseline

### The research story (chronological)

| # | Problem observed | Hypothesis | What we tried | Result | Lesson / decision |
|---|---|---|---|---|---|
| 0 | IDRiD has duplicates and conflicting labels | evaluation would be misleading | audit + clean protocol (Part 7) | 404/102 clean split | **Integrity before modelling** (ADR-001) |
| 1 | Which backbone? | a pretrained CNN with a linear head is a fair first baseline | prior study: ResNet50, EfficientNet-B0, ConvNeXt-T, Swin-T, frozen and partially tuned, 224 px, 3 folds × 2 seeds on the 404 clean train | frozen ConvNeXt-T best: macro-F1 0.506, QWK 0.774 | ConvNeXt-T chosen as baseline; Grade-1 recall only 16.7% → "not a final classifier" |
| 2 | MA undetected by the four-lesion model | MA needs a specialist model | SegFormer-B0 (4 lesions) + MA-only U-Net, full 512 vs native patches | SegFormer mean Dice 0.324 but MA Dice 0; MA U-Net full512 Dice 0.287 vs patches 0.169 | keep separate MA model; patches raise recall but flood false positives |
| 3 | Need a working app fast | ship a prototype, swap models by rule later | **v0**: frozen ConvNeXt-T @224, 6 cross-validation heads, + segmenters (ADR-009) | app works; but its heads had seen IDRiD-val (in-sample QWK 0.98) | in-sample score invalid → clean comparator built (ADR-010) |
| 4 | Fair comparator | dev-train-only frozen heads | `frozen_convnext224_devtrain_v1` | IDRiD-val QWK 0.795, APTOS-val 0.720 | becomes the baseline every new grader must beat (ADR-013) |
| 5 | Is fine-tuning on IDRiD alone enough? | fine-tuning beats frozen features | ConvNeXt-T and EfficientNet-B3, CE vs regression, Ben Graham vs plain, 384/512, trained on 303 IDRiD images | best: ConvNeXt-T reg (Ben Graham) 384 → IDRiD 0.819 but APTOS only 0.518; EfficientNet-B3 much worse (APTOS 0.06–0.48) | IDRiD alone does not generalise → need more, varied data |
| 6 | Would a retina-specific foundation model help? | RETFound features beat ImageNet features | matched frozen linear probes, ConvNeXt-T vs RETFound ViT-L, 224 px (ADR-012) | small gains, CIs include 0 | RETFound **not adopted** (Part 17) |
| 7 | More data | mixing IDRiD + APTOS + MMRDR helps | full fine-tune of ConvNeXt-T on 14,063 images; screen reg384 / reg512 / CE384 on the inner hold-out (ADR-015) | inner QWK 0.929 / 0.928 / 0.918 | reg384 fixed as the candidate before validation |
| 8 | Is the candidate really better? | yes, by a pre-registered paired-bootstrap rule | ADR-013 vs the frozen comparator | ΔQWK +0.098 [+0.036, +0.171] IDRiD-val; +0.198 [+0.152, +0.247] APTOS-val | **swapped into the app** (`queue/decisions/a2_swap.json`) |
| 9 | Raw scores are not probabilities | calibrate on held-out data | Platt + isotonic + τ on the inner hold-out (ADR-019) | τ = 0.55, AUROC 0.992 / 0.975 | calibration + deferral in the app |
| 10 | Can we safely route some eyes to routine rescreening? | yes, with a pre-registered miss-rate bound | policy (c), thresholds fitted on the hold-out (ADR-039/040) | dev: IDRiD 2/63, APTOS 1/201 missed at 2.5% | routing built, pending locked test |
| 11 | Would extra signals help routing? | disagreement, OOD, referable head, ensemble | Step 4 (ADR-041/042) | all abandoned or not testable; explanation faithfulness supported | nothing added to the decision path |
| 12 | Better lesion model (A3) | U-Net/R18 trained with DDR | 5-fold CV planned | folds 0–1 trained; fold 2 stalled (GPU driver fault); **cancelled by owner** | segmenter stays v0.1 |
| 13 | Does it hold on locked data? | — | freeze rc-1, run IDRiD test and DeepDRiD once (ADR-043/045/046) | grading holds moderately; routine routing fails on IDRiD test | **routing hypothesis rejected for autonomous use** |

Planned but **not run** (cancelled by owner, `queue/jobs.yaml`): threshold re-fit for macro-F1 (S1), stage specialists (S2/S3), CORN
ordinal head (S4), test-time augmentation, lesion-to-grade fusion (A4), pseudo-labelling, EyePACS, seed 41 / 3-seed ensemble, and the
R2/R3/R4 safety checks. Do not present these as results.

### Part 10 — The early ConvNeXt baseline [EXPERIMENT]

**Two different "early baselines" exist; keep them apart.**

1. **Prior-study cross-validation baseline** (`outputs/metrics/model_selection/grading_scorecard.csv`, CLAIMS_LEDGER C05/C06):
   ConvNeXt-Tiny, ImageNet-pretrained, **backbone frozen**, linear five-grade head, 224-px aspect-preserved input, standard ImageNet
   normalisation, cross-entropy. Six runs (3 folds × 2 seeds) on the 404 clean IDRiD train images.
   - macro-F1 **0.506**, QWK **0.774**, Grade-1 recall **16.7% (3/18)**, ECE 0.237. ✓ verified.
   - Same study, frozen 224: EfficientNet-B0 0.489 / 0.714; Swin-T 0.485 / 0.720; ResNet50 0.458 / 0.684 (macro-F1 / QWK).
2. **App comparator** `frozen_convnext224_devtrain_v1` (registry): same idea, trained on dev-train 303 only, evaluated on the held-out
   validation sets: IDRiD-val QWK **0.795**, macro-F1 0.462; APTOS-val QWK **0.720**, macro-F1 0.338.

**"Frozen backbone" in simple words.** The big pretrained network is used as a fixed feature extractor ("a camera that describes the
photo in 768 numbers"); only a small final layer is trained to turn those numbers into a grade.

**Why it was useful.** Cheap, fast, stable, hard to overfit on 300 images, and a fair yardstick.

**Why it was insufficient.** ImageNet features were never trained on retinas; mild disease (Grade 1) was almost never recognised, and
the scores were miscalibrated (ECE ≈ 0.24).

---

## Part 11 — The active ConvNeXt-Tiny grader

**[IMPLEMENTED]** — `configs/app/app.json` → `models/checkpoints/phase2/graders/convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt`
(SHA-256 `acf53697…`, ADR-045).

| Property | Value | How verified |
|---|---|---|
| Architecture | `timm` `convnext_tiny.fb_in1k` | checkpoint JSON `arch` |
| Pretrained source | ImageNet-1k (`fb_in1k` weights via timm) | `build(..., pretrained=True)` in `src/train/finetune_mixed.py` |
| Training type | **full fine-tuning** (all layers trained), layer-wise learning rates | `param_groups` |
| Total parameters | **27,820,897** | counted from the state dict and from timm (identical) |
| Trainable parameters | 27,820,897 (all) | full fine-tune |
| Head | `head.fc`: 768 → 1 (769 parameters) | state dict shape (1, 768) |
| Output | **one scalar** severity score | `head = "reg"` |
| Input | 384 × 384 RGB, FOV-cropped | checkpoint JSON `size`, `preprocessing: plain` |
| Checkpoint file | **111,363,403 bytes (≈ 106 MiB)**, float32 | `stat` on disk |
| Training time / peak VRAM | 5,536 s (≈ 92 min) / 1,211 MiB | checkpoint JSON |

**ConvNeXt in easy language.** A modern convolutional neural network: early layers detect edges and colours, middle layers textures and
small shapes (dots, vessel edges), late layers combine them into retina-level patterns. "Tiny" is the smallest of the family.

**Why Tiny was practical.** It fine-tunes on a 4 GB laptop GPU (RTX 3050) in about 1.5 hours with AMP and gradient checkpointing, and
runs at about 1 second per image (`results/benchmark.json`). We do **not** claim it is clinically optimal; Part 16 explains the choice.

---

## Part 12 — Why regression instead of five-class softmax

**Simple.** DR stages are ordered. Calling a stage-3 eye "stage 2" is a smaller mistake than calling it "stage 0". A single severity
number on a line respects that order; five unrelated boxes do not.

**Technical.** The model outputs one number *s*. Training uses Smooth-L1 loss between *s* and the integer grade. At inference *s* is
compared with four cut points fitted on the inner hold-out (Nelder–Mead, maximising QWK; `fit_thresholds` in `src/train/finetune_grader.py`):

| Cut point | Value (checkpoint JSON) |
|---|---|
| t1 (0 \| 1) | 0.52702448 |
| t2 (1 \| 2) | 1.40838036 |
| t3 (2 \| 3) | 2.63552623 |
| t4 (3 \| 4) | 3.46447762 |

Rule: *s* < 0.527 → stage 0; 0.527 ≤ *s* < 1.408 → stage 1; 1.408 ≤ *s* < 2.636 → stage 2; 2.636 ≤ *s* < 3.464 → stage 3; *s* ≥ 3.464 → stage 4.
Example: *s* = 2.0 → stage 2; *s* = 3.5 → stage 4.

**Evidence that regression helped:** in the A2 screen, regression @384 reached inner QWK 0.929 vs cross-entropy @384 0.918 (ADR-015).

**Why the API "probabilities" are not real probabilities.** For a regression grader the pipeline sets the probability vector to
**one-hot** (1.0 on the chosen stage, 0 elsewhere; `_summarise` in `src/inference/finetuned.py`). The saved prediction files show
exactly that (`p3 = 1.00000`). The `referable_probability` field inside `grading` is therefore 0 or 1. The meaningful probability is
the **calibrated P(referable)** from the assist layer (Part 29).

---

## Part 13 — Exact preprocessing

| Step | Training (`src/train/finetune_mixed.py` `cached`/`to_input`) | Runtime (`Pipeline.analyze` → `FinetunedGrader.tensor`) | Why |
|---|---|---|---|
| Load | `ImageOps.exif_transpose(im).convert("RGB")` | same | phones/cameras store rotation in EXIF; models need 3-channel RGB |
| FOV crop | `fov_box`: downscale to 512 wide, pixels with max channel > 15 are retina, take the bounding box | same function | remove useless black background |
| Square pad | `ImageOps.pad` to a centred square, black | same | avoid stretching the round retina (geometric distortion) |
| Resize | bilinear to 384 × 384 | same | make input computationally manageable |
| Scale | ÷ 255 | ÷ 255 | 0–1 range |
| Normalise | ImageNet mean (0.485, 0.456, 0.406), std (0.229, 0.224, 0.225) | same constants | match the statistics the pretrained network expects |
| Augment | train only: random h/v flips, rotation U(−180°, 180°), scale U(0.95, 1.05), brightness/contrast ±10% | none | robustness to orientation and exposure |

Training and runtime match (checked in code). The trade-off: the resize makes training feasible but can erase tiny lesions (Part 8).
The lesion models use a different input: letterbox to 512 × 512 (`letterbox` in `src/inference/pipeline.py`).

---

## Part 14 — Active training data

**Grading pool = 14,063 images** (checkpoint JSON `train_data`):

| Source | Images |
|---|---|
| IDRiD dev-train | 303 |
| APTOS-train | 2,929 |
| MMRDR-train | 10,831 |
| **Total** | **14,063** |

**Inner split** (stratified by dataset × grade, 80/20): **11,250 for optimisation** and **2,813 inner hold-out**
(`configs/calibration/app_grader.json`: "fine-tuner inner hold-out (2813 images)"; 905 of them referable, `results/coverage/step2_baseline.json`).

**Why not just merge the datasets blindly?**
- **Balance:** MMRDR is 77% of the pool. Sampling is **dataset-balanced** (each dataset gets a similar share per epoch) so IDRiD and APTOS
  are not drowned out.
- **Class imbalance:** grade weights are 1/√(count of that dataset × grade), a softened rebalance that boosts rare grades without
  over-weighting a handful of images.
- **Domain differences:** different cameras and resolutions; mixing is the point, but per-dataset QWK is tracked every epoch.
- **Label harmonisation:** all three use the ICDR 0–4 scale; label quality differs (APTOS one grader).
- **Lineage:** MMRDR derives from OIA-DDR, so DDR cannot later be an independent grading test (Part 32).
- **Validation separation:** validation and locked images were never in the pool; near-copies were removed by hash.

**Four kinds of data, in plain words**

| Kind | What it is for | Who sees it |
|---|---|---|
| Training (11,250) | the model learns from it | optimiser |
| Inner hold-out (2,813) | choose the best epoch, fit grade cut points, fit calibration and routing thresholds | never trained on |
| Development validation (IDRiD-val 101, APTOS-val 518) | compare candidates by pre-written rules; report development numbers | never trained or tuned on |
| Locked test (IDRiD clean test 102, DeepDRiD 1,988) | one final evaluation of the frozen system | opened once, after `rc-1` |

---

## Part 15 — Exact training parameters

All from `src/train/finetune_mixed.py` and the checkpoint JSON (`hyper`, `history`).

| Parameter | Value | What it is | Why we used it |
|---|---|---|---|
| Loss | Smooth-L1 (Huber) on score vs grade | error measure for a number | regression; less sensitive to outliers than squared error |
| Optimiser | AdamW | adaptive gradient descent with decoupled weight decay | standard for ConvNeXt fine-tuning |
| Base learning rate | 2e-4 | step size | moderate for fine-tuning |
| Layer-wise LR multipliers | stem/stage0 ×0.25, stage1 ×0.4, stage2 ×0.6, stage3 ×0.8, head ×5 | early layers learn slower | keep generic pretrained features, adapt late layers and the new head faster |
| Weight decay | 0.05 | pulls weights toward zero | regularisation |
| Micro-batch | 16 | images per GPU step | fits 4 GB VRAM |
| Gradient accumulation | 2 | add gradients of 2 micro-batches | effective batch **32** without more memory |
| Gradient clipping | max norm 2.0 | caps update size | stability |
| Mixed precision (AMP) | yes, with GradScaler | 16-bit maths where safe | speed and memory |
| Gradient checkpointing | yes | recompute activations instead of storing them | memory |
| Schedule | 1 warm-up epoch (linear), then cosine to 0 | learning-rate curve | stable start, smooth finish |
| Max epochs | 15 | passes over (resampled) training data | budget |
| Early stopping | patience 4 on (inner QWK, macro-F1) | stop if no improvement | avoid overfitting |
| Best epoch | index 14 = **the 15th (last) epoch**; early stopping never triggered | — | note: ADR-015 writes "epoch 14" in 0-based terms |
| Seed | 17 | randomness | reproducibility |
| Sampling | weighted with replacement; dataset balance × 1/√(dataset-grade count) | which images per epoch | imbalance |
| Augmentation | flips, rotation ±180°, scale 0.95–1.05, brightness/contrast ±10% (on GPU) | random changes to training images | fundus photos can be rotated or exposed differently |
| Checkpoint selection | best (inner QWK, macro-F1) at default cut points 0.5/1.5/2.5/3.5 | which weights to keep | chosen on the hold-out, never on validation |
| Cut points | Nelder–Mead on the hold-out, maximise QWK | turn score into stage | final inner QWK 0.929, macro-F1 0.716 |

---

## Part 16 — Why ConvNeXt-Tiny?

Do **not** say "ConvNeXt was the best model". Say how the decision was made.

**Experimental evidence**
- In the prior 4-backbone study (frozen and partial tuning, 224 px), ConvNeXt-T had the highest macro-F1 and QWK (0.506 / 0.774 frozen;
  0.507 / 0.775 partial) versus ResNet50, EfficientNet-B0 and Swin-T (`grading_backbone_selection.json`).
- In the phase-1 fine-tune screen on IDRiD dev-train, ConvNeXt-T beat EfficientNet-B3 in every matched pair (e.g. regression @384 with
  Ben Graham: IDRiD 0.819 vs 0.631; APTOS 0.518 vs 0.482). EfficientNet-B3 also showed unstable BatchNorm statistics (decision text in
  `backend/app.py` model card).
- Against RETFound (frozen probes), the pre-registered rule did not show a significant gain for RETFound (Part 17).
- The fine-tuned regression ConvNeXt-T passed the ADR-013 swap rule against the frozen comparator with clear margins.

**Engineering reasons**
- pretrained weights readily available in `timm`;
- trains on a 4 GB GPU; inference ≈ 1 s/image on GPU, ≈ 1.4 s on CPU;
- stable training; ordinal regression head is a one-line change;
- hackathon time limits favoured improving one working pipeline over swapping architectures.

**What was not established.** We did not compare every modern architecture under full fine-tuning on the mixed pool. "ConvNeXt-T was
the best of what we tested under our constraints" is accurate; "ConvNeXt is optimal for DR" is not.

---

## Part 17 — The RETFound experiment

**[EXPERIMENT; not adopted]** — ADR-012, registry rows `feathead…`, `results/audit/retfound_check.json`.

**What RETFound is.** A retinal foundation model: a ViT-Large/16 trained with masked-autoencoder self-supervision on a very large
collection of retinal images (paper: 904,170 colour fundus photographs; CLAIMS_LEDGER C11, Zhou et al., Nature 2023). We used the
pretrained CFP weights `YukunZhou/RETFound_mae_natureCFP`.

| Property | Value |
|---|---|
| Encoder | ViT-L/16, **303,301,632** parameters (counted with timm `vit_large_patch16_224`, `num_classes=0`) |
| Weights file on disk | 3,952,489,221 bytes (≈ 3.7 GiB; includes optimiser state and MAE decoder) |
| Input | 224 × 224, same FOV crop and ImageNet normalisation as ConvNeXt |
| Our use | frozen backbone + linear head, 3 seeds, inner 20% hold-out |

**Matched frozen probes, trained on IDRiD dev-train + APTOS-train** (registry):

| Metric | ConvNeXt-T probe | RETFound probe |
|---|---|---|
| IDRiD-val QWK | 0.7398 | 0.7693 |
| IDRiD-val macro-F1 | 0.4041 | 0.4519 |
| APTOS-val QWK | 0.8616 | 0.8817 |
| APTOS-val macro-F1 | 0.6029 | 0.6887 |
| IDRiD-val Grade-1 / Grade-4 recall | 0.000 / 0.333 | 0.000 / 0.333 |
| APTOS-val Grade-1 / Grade-4 recall | 0.560 / 0.538 | 0.600 / 0.615 |
| Severe under-grading (3–4 → 0–1), IDRiD / APTOS | 0.033 / 0.046 | 0.000 / 0.078 |

**The decision rule (pre-registered):** adopt RETFound only if the ΔQWK confidence interval is above 0 on at least one set, not worse on
the other, and severe under-grading does not increase.
- ΔQWK (RETFound − ConvNeXt): **+0.030 [−0.065, +0.129]** on IDRiD; **+0.020 [−0.018, +0.061]** on APTOS → both intervals include 0
  → **rule fails**.
- ΔMacro-F1 on APTOS +0.086 [+0.016, +0.155] was significant, but it was not the pre-registered metric.
- Trained on IDRiD only, RETFound generalised much worse to APTOS (QWK 0.19 vs 0.68).
- A sanity check with RETFound's official pooling changed nothing material (ADR-012 addendum).

**How to say it.** RETFound showed promising improvements on some metrics. We did **not** prove RETFound is worse. We did not have
enough evidence, under our pre-written rule, to replace a working ConvNeXt pipeline, and fully fine-tuning a ViT-L does not fit our
4 GB GPU. With more compute, RETFound fine-tuning is a reasonable next experiment.

---

## Part 18 — Model size comparison

| Model | Parameters | Checkpoint on disk | Input | Training type | Compute implication | Role |
|---|---|---|---|---|---|---|
| **Active grader** ConvNeXt-T regression | 27,820,897 | 111,363,403 B | 384 | full fine-tune | fits 4 GB GPU with AMP + checkpointing | [IMPLEMENTED] |
| Seed-23 replica of the grader | 27,820,897 | 111,363,403 B | 384 | full fine-tune | — | [EXPERIMENT] (ensemble not testable) |
| Referable-head variant (`regbin`) | 27,821,666 (2 outputs: score + referable logit) | 111,367,103 B | 384 | full fine-tune | — | [EXPERIMENT, abandoned] |
| Early frozen ConvNeXt-T @224 | backbone 27,820,128 frozen + linear head | head file 24,235 B (+ shared backbone 114,419,221 B `convnext_tiny-983f1562.pth`) | 224 | frozen + linear | very cheap to train | [EXPERIMENT] baseline |
| RETFound ViT-L/16 | 303,301,632 (encoder) | head 31,373 B; weights file 3,952,489,221 B | 224 | frozen + linear | full fine-tune would not fit 4 GB | [EXPERIMENT, not adopted] |
| EfficientNet-B3 | 10,697,769 (1 output) | ≈ 43.4 MB (e.g. 43,388,547 B) | 384/512 | full fine-tune (IDRiD only) | — | [EXPERIMENT, rejected] |
| ResNet50 / EfficientNet-B0 / Swin-T | 23,518,277 / 4,013,953 / 27,523,199 (5 outputs) | 94,402,577 / 16,371,195 / 110,396,268 B (partial-tuning checkpoints) | 224 | frozen / partial | — | [EXPERIMENT] prior study |
| **SegFormer-B0** (4 lesion channels; HE/EX/SE used) | 3,451,748 | 13,884,449 B | 512 | trained 6 epochs, 40 images | light | [IMPLEMENTED] |
| **MA U-Net / ResNet18** | 12,461,009 | 49,961,003 B | 512 | trained 12 epochs, 40 images | light | [IMPLEMENTED] |

**Parameter count ≠ checkpoint size ≠ runtime memory.** Parameters are the number of learned weights. The checkpoint file is about
4 bytes × parameters for float32, plus metadata; a "training" checkpoint may also hold optimiser state (that is why the RETFound file is
3.7 GiB for a 303 M-parameter encoder). Runtime memory adds activations, which grow with image size: the whole app used **363 MB** peak
VRAM per analysis (`results/benchmark.json`) while the grader's *training* peaked at 1,211 MiB.

**Bigger is not automatically better.** RETFound has ~11× ConvNeXt-T's parameters, yet its gain was not statistically supported here.
Larger models need more data, more compute and are harder to run in a clinic.

---

## Part 19 — Development grading results

**Active grader on the development validation sets** — registry runs `20261029-083502` (IDRiD-val) and `20261029-083933` (APTOS-val);
agreement runs `20261029-200713/200721`; ranking from `configs/calibration/app_grader.json`.

| Metric | IDRiD-val (n = 101) | APTOS-val (n = 518) |
|---|---|---|
| QWK [95% CI] | **0.893 [0.846, 0.929]** | **0.918 [0.896, 0.938]** |
| Macro-F1 | 0.545 | 0.628 |
| Accuracy (exact stage) | 0.673 | 0.811 |
| Within one stage | 98.0% | 98.1% |
| Referable sensitivity (stage ≥ 2) | 93.7% | 95.0% |
| Referable specificity | 100.0% | 90.5% |
| AUROC of calibrated P(referable) | 0.992 | 0.975 |
| Severe under-grading (true 3–4 → 0–1) | 0.000 | 0.015 |

**Per-grade recall (do not hide the weak classes)**

| Grade | IDRiD-val | APTOS-val |
|---|---|---|
| 0 | 0.939 (31/33) | 0.993 (265/267) |
| 1 | **0.200 (1/5)** | **0.380 (19/50)** |
| 2 | 0.697 (23/33) | 0.759 (104/137) |
| 3 | 0.500 (9/18) | 0.400 (10/25) |
| 4 | **0.333 (4/12)** | 0.564 (22/39) |

**Confusion matrices** (rows = true grade, columns = predicted grade; from the saved prediction files):

```
IDRiD-val            APTOS-val
 31  2  0  0  0      265   2   0   0   0
  4  1  0  0  0        1  19  27   2   1
  1  3 23  6  0        0   9 104  24   0
  0  0  9  9  0        0   0  11  10   4
  0  0  1  7  4        0   1   6  10  22
```

These are **development** numbers: candidates were compared on these sets (by pre-written rules), so they are optimistic relative to a
locked test. Compare with Part 30.

---

## Part 20 — Every metric explained for beginners

**Accuracy.** *Simple:* what fraction of predictions were exactly right. *Why misleading:* if 90% of eyes are stage 0, a model that always
says "0" scores 90% and is useless. *Example:* IDRiD-val accuracy 0.673 = 68 of 101 exactly right.

**Precision.** "When the model says class X, how often is it right?" *Example:* if it calls 10 eyes stage 4 and 8 are, precision 0.8.

**Recall / sensitivity.** "Of all true class-X cases, how many did we catch?" *Why it matters for screening:* a missed referable eye is a
person who goes home untreated. Our headline referable sensitivity is about 90–95%.

**Specificity.** "Of all true negatives, how many did we correctly leave negative?" Low specificity means many unnecessary referrals,
which costs specialist time.

**Macro-F1.** F1 combines precision and recall for one class; *macro* averages it over the five classes **equally**, so rare stages (1
and 4) count as much as common ones. That is why our macro-F1 (0.55–0.63) looks much lower than accuracy.

**QWK — quadratic weighted kappa.** *Simple:* getting stage 3 wrong as stage 2 is bad, but getting it wrong as stage 0 is much worse. QWK
knows the difference. *Technical:* kappa measures agreement beyond chance; "quadratic weighted" gives each disagreement a penalty
proportional to the **square** of the distance between grades (1 step → weight 1, 3 steps → weight 9, relative). 1 = perfect agreement,
0 = chance. *In DrishtiQ:* our stages are ordered, so QWK is the main grading metric in every decision rule. For context, published
inter-grader κ for DR grading is reported around 0.40–0.65 (CLAIMS_LEDGER C17, Krause et al. 2018; a published figure, not ours).

**AUROC.** *Simple:* if you pick one referable eye and one non-referable eye at random, how often does the model give the referable eye
the higher risk? 0.5 = coin flip, 1 = perfect ranking. *Warning:* AUROC measures ranking across all thresholds; **a high AUROC does not
guarantee no dangerous individual errors**. Our locked IDRiD AUROC is 0.943 and we still routed a grade-3 eye to routine.

**Dice.** Overlap between the predicted lesion pixels and the expert mask: 2 × overlap / (predicted + expert). 1 = perfect, 0 = no overlap.

**AUPR.** Area under the precision–recall curve. Useful for sparse lesions where almost all pixels are background: a model can get
99.9% pixel accuracy by predicting "no lesion" everywhere, but its AUPR will be near zero.

**Calibration.** When the model says "70%", the event should happen about 70% of the time. ECE (expected calibration error) measures the
average gap.

**Confidence interval.** A range of plausible values given our sample size. *Example:* IDRiD-val QWK 0.893 [0.846, 0.929] — with 101
images we cannot pin it more precisely. If two models' difference has an interval like [−0.065, +0.129], the data are consistent with
"no difference", so we cannot claim one is better. *Exact upper bound* (Clopper–Pearson): with 5 misses out of 63, the true miss rate
could plausibly be as high as 17.6%.

---

## Part 21 — The Grade-1 problem

**Verified facts** (confusion matrices in Part 19):
- **IDRiD-val:** 5 Grade-1 eyes; **1 correct, 4 called Grade 0** → mostly *under-calling* mild disease.
- **APTOS-val:** 50 Grade-1 eyes; **19 correct; 1 → 0, 27 → 2, 2 → 3, 1 → 4** → mostly *over-grading* to Grade 2.
- Locked IDRiD test: 5 Grade-1 eyes, **0 correct** (3 → 0, 2 → 2). DeepDRiD: recall 0.440.
- Prior baseline: Grade-1 recall 16.7% (3/18).

These are different failure patterns, so there is no single cause. **Hypotheses (not proven):**
- microaneurysms are a few pixels at 384 px (Part 8) → under-calling (CLAIMS_LEDGER H02);
- label differences: APTOS is single-grader; the mild/moderate boundary is subjective;
- domain differences between datasets;
- class imbalance (Grade 1 is a small share of every set);
- the scalar cut point t1/t2 sits where the score distributions overlap;
- dataset-balanced sampling changes the effective prior per dataset.

With only 5 Grade-1 eyes in IDRiD-val, no fix can be measured reliably there.

---

## Part 22 — The Grade-4 / PDR problem

**Verified:** IDRiD-val Grade-4 recall **4/12** (1 → 2, 7 → 3); APTOS-val **22/39** (1 → 1, 6 → 2, 10 → 3). Locked IDRiD test 5/13;
DeepDRiD 0.643. Most misses become **Grade 3**.

**Architectural limitation.** The grader produces one severity number from a 384-px image. Nothing in DrishtiQ explicitly detects
neovascularisation, vitreous/preretinal haemorrhage or other advanced vascular signs. Our lesion models cover MA/HE/EX/SE only.
Therefore **our lesion segmentation cannot prove or rule out PDR**, and the explanation module says so in its "Limits" sentence ("This
tool cannot see new vessel growth. A doctor must rule out Stage 4."). Grade-3 and Grade-4 eyes are both routed to expedited review, so a
3-vs-4 error does not lower urgency in the app.

---

## Parts 23–24 — Segmentation pipeline and results

**[IMPLEMENTED] app segmenter v0.1** (`LesionSegmenter`, `V0Segmenter` in `src/inference/pipeline.py`; checksums in ADR-041/045)

| Lesion | Model | Params | File size | Input | Loss | Training data | Post-processing (pp_v2) |
|---|---|---|---|---|---|---|---|
| MA | U-Net, ResNet18 encoder (ImageNet), decoder (128, 64, 32, 16, 16) | 12,461,009 | 49,961,003 B | letterbox 512 | 0.5 weighted BCE (pos. weight ≤ 50) + 0.5 Tversky (α 0.3, β 0.7) | 40 IDRiD seg images, 12 epochs, AdamW lr 3e-4, FP32 | threshold 0.7, min area 40 px, optic disc masked |
| HE | SegFormer-B0 (MiT-B0), 4 output channels | 3,451,748 | 13,884,449 B | letterbox 512 | BCE + Dice | 40 IDRiD seg images, 6 epochs, AdamW lr 3e-4 | threshold 0.5, min area 20 px |
| EX | same SegFormer-B0 | — | — | — | — | — | threshold 0.7, optic disc masked |
| SE | same SegFormer-B0 | — | — | — | — | — | threshold 0.4, min area 200 px |

The SegFormer also outputs an MA channel, which is replaced by the MA U-Net. Areas in pp_v2 are measured at 4,288 px width. pp_v2 was
chosen on 5-fold out-of-fold maps of the 50 dev segmentation images under the rule "no more false-positive regions on grade-0 images
than without post-processing" (ADR-011). Sources: `configs/experiments/seg_Segformer_full512_bce_dice_s17.json`,
`configs/experiments/ma_Unet_full512_weighted_bce_tversky_e12_s17_fp32.json`, `configs/postprocess/pp_v2.json`.

**Results** (registry `20261028-223254-segment-v0+pp_v2` and `20261029-085218-segment-v0+pp_v2`)

| Lesion | IDRiD-val Dice | Precision | Recall | AUPR | images with mask | DDR-test AUPR (n = 225) | False-positive regions per grade-0 image (mean) |
|---|---|---|---|---|---|---|---|
| MA | 0.275 | 0.363 | 0.221 | 0.191 | **10** | 0.053 | 2.8 |
| HE | 0.422 | 0.515 | 0.358 | 0.363 | **10** | 0.163 | 2.2 |
| EX | 0.559 | 0.622 | 0.508 | 0.550 | **10** | 0.352 | 8.1 |
| SE | 0.447 | 0.509 | 0.398 | 0.353 | **5** | 0.105 | 2.5 |

**These are not production-grade lesion validation results:** 10 images (5 for SE), and that validation split is fold 4 of the
cross-validation used to choose post-processing, so it is not independent of the selection (ADR-011 caveat). DDR-test numbers are much
lower: a different domain and the first independent check of the lesion models. The planned better model (A3) was cancelled.

---

## Part 25 — Why microaneurysms are hard

- **Tiny:** often 10–20 pixels across at native resolution, a few pixels after resizing (Part 8).
- **Look-alikes:** vessel crossings, small haemorrhages, dust, noise and reflections.
- **Extreme imbalance:** almost all pixels are background.
- **Little pixel-level data:** 40 training images with MA masks in the prior study.

**The patch experiment [EXPERIMENT]** (`outputs/metrics/model_selection/MA_specialist_scorecard.csv`; 10 validation images, 2 seeds):

| Approach | MA Dice | Pixel recall | Pixel precision |
|---|---|---|---|
| whole image, 512 (active) | **0.287** | 0.273 | 0.303 |
| native-resolution 256 patches | 0.169 | **0.729** | 0.098 |

Patches kept more pixels and found far more microaneurysms, but produced many false positives. **Lesson:** preserving detail alone does
not solve the problem; local patches lose global/anatomical context (vessels, disc, normal texture) that separates a real MA from a
look-alike. A confound: patch sampling was 50% lesion-centred, which shifts the prior (CLAIMS_LEDGER H03). This motivates the global +
local idea in Part 26.

---

## Part 26 — The global + local idea (proposed)

**[PROPOSED FUTURE ARCHITECTURE — NOT CURRENTLY VALIDATED]**

```
HIGH-RES FUNDUS
      ↓
RETINAL FOREGROUND (field of view)
      ↓
ANATOMY MAP (optic disc, fovea/macula, large vessels)
      ↓
┌──────────────────────┬────────────────────────────┐
│ GLOBAL VIEW           │ LOCAL VIEW                  │
│ whole retina, low res │ high-res crops, selected    │
│ severity + context    │ tiny lesions (MA, small HE) │
└──────────┬───────────┴──────────────┬─────────────┘
           └──────── evidence comparison ────────┘
```

**Why not blindly tile the whole image?** All tiles at native resolution means more computation, many redundant tiles of empty retina, more
chances for false positives (the patch experiment), and no global context per tile.

**Candidate-guided, anatomy-aware selection.** Use the global view and anatomy map to choose a small number of high-resolution regions (e.g.
around the macula, along vessel arcades, around global-model candidates) and analyse those at native resolution.

**The critical test.** The patch selector itself must be evaluated: **what fraction of expert-annotated lesions fall inside the selected
patches (lesion retention / recall)?** A selector that skips a region silently creates misses that no downstream model can recover.

---

## Part 27 — Quality and gradability

**[IMPLEMENTED] heuristic quality check** (`Pipeline.quality`, `configs/quality/quality_v1.json`):

| Check | Rule | Result |
|---|---|---|
| Field of view | fraction of pixels with max channel > 15 (at 512 px) < 0.2 | **rejected** (not analysed) |
| Corner darkness | dark-corner score < 0.55 (fitted on 900 training images + 64 synthetic non-fundus images; ADR-023) | "may not be a fundus photograph" |
| Colour | red not dominant over blue inside the field | "atypical colour" |
| Brightness | mean green < 25 or > 200 | under/over-exposed |
| Sharpness | variance of the Laplacian of the smoothed green channel < 0.5 | "blurred; small lesions may be missed" |

Any issue → `usable = false` → state **RETAKE** (after a second failed attempt for the same eye → clinician review).

**Evidence about how good it is**
- R1 robustness (development): strong blur, low contrast and very dark photos are flagged on 70–100% of images; photos **downscaled to
  640 px** are flagged only 2% and 4 of 63 referable IDRiD-val images were then routed to routine (`results/robustness/r1_robustness.json`, ADR-042).
- Locked DeepDRiD: agreement with DeepDRiD's own "overall quality" label **53.6%**; it flags only **16.3%** of images labelled poor
  (and 3.8% of those labelled good).
- R2 (non-fundus inputs) and R4 (DDR ungradable images) were **not run**.

**Do not call it a validated gradability model.** It is a set of image heuristics.

**[PROPOSED] Task-aware gradability.** An image can be good enough to see a large haemorrhage but not to rule out tiny microaneurysms.
Instead of one "usable / not usable" decision, estimate *for which tasks* an image is adequate (e.g. "adequate for referable-DR
grading; inadequate for MA detection"). This is a research concept, not built.

---

## Part 28 — Grad-CAM

**[IMPLEMENTED]** (`FinetunedGrader.grade_with_cam`, `src/inference/finetuned.py`):
1. a forward hook stores the activations of the **last ConvNeXt stage**;
2. the gradient of the **regression score** with respect to those activations is computed by back-propagation;
3. each channel's weight = mean gradient over space; map = ReLU(Σ weight × activation);
4. the map is mapped back from the 384-px square to the image, masked to the retina and normalised; the UI shows it as "Where the AI looked".

**What it means:** regions whose features *increased* the severity score. **What it does not mean:** "the highlighted area is definitely
disease". It can highlight the optic disc, reflections or borders.

| Concept | Question it answers |
|---|---|
| **Grad-CAM** | where did the grading model's evidence come from? (model attribution) |
| **Segmentation** | which pixels does a lesion model predict as lesion X? (predicted localisation) |
| **Expert mask** | what did a human annotator mark? (reference annotation) |

Supporting evidence [EXPERIMENT, Step 4e, development data]: hiding the lesions an explanation cites lowered the grader's score more than
hiding an equal random area (median drop 0.295 vs −0.016 on IDRiD-val, n = 59, p = 4.5e-6; 0.235 vs −0.013 on APTOS-val, n = 221,
p = 4.3e-17; `results/faithfulness.json`). The planned Grad-CAM shortcut audit (R3) was **not run**.

---

## Part 29 — Calibration and uncertainty

**[IMPLEMENTED]** (`configs/calibration/app_grader.json`, `src/inference/assist.py`, ADR-019; fitted on the 2,813-image inner hold-out)

| Output | How | Value |
|---|---|---|
| **P(referable)** = chance the eye is stage ≥ 2 | Platt scaling (logistic regression on the score) | P = 1 / (1 + e^−(3.1194 × s − 4.5339)) |
| **Stage confidence** = chance the exact stage is right | isotonic regression of "stage correct" on the distance from the score to the nearest cut point | 0–1 |
| **Deferral threshold τ** | smallest value in {0.50 … 0.95} giving ≥ 85% accuracy on retained hold-out images | **τ = 0.55** |
| **Routing threshold** (default 2.5% target) | largest P(referable) threshold with hold-out miss rate ≤ 2.5% | P(referable) < **0.13603** (score < 0.861) |
| Routing threshold (5% option) | same at 5% | P(referable) < 0.31741 |

Example: score 1.5 → P(referable) ≈ 54%; score 0.05 → P(referable) ≈ 1.2%.

**Development calibration** (ECE, uncalibrated → calibrated): P(referable) IDRiD-val 0.040 → **0.083 (worse)**, APTOS-val 0.077 → 0.027;
stage confidence IDRiD-val 0.154 → 0.116, APTOS-val 0.088 → 0.044. Deferral on development data: IDRiD-val 8.9%, APTOS-val 6.4%.

**Four different ideas — keep them apart**
- **Prediction:** which stage the model chose.
- **Confidence:** how strongly the model's internal evidence supports that choice.
- **Calibrated probability:** whether that confidence historically matched observed outcomes on held-out data.
- **Clinical certainty:** much broader (history, other findings, follow-up). No single number from a classifier represents it.

**Confidence is not correctness — from our own locked test.** IDRiD_060, a true **grade 3** eye, was called **stage 0** with stage
confidence **0.956** and P(referable) ≈ 1.2%. On DeepDRiD, 44 of the 60 referable images called non-referable had stage confidence
≥ τ (5 of them ≥ 0.85).

---

## Part 30 — The locked IDRiD test

**[EXPERIMENT on the frozen system]** — `results/locked/idrid_test.json`, ADR-043 (protocol written before), ADR-046 (results).

102 clean test images, never used for training, tuning, threshold fitting or selection; evaluated **once** on `rc-1`.

| Metric | Value [95% CI] |
|---|---|
| QWK | **0.816 [0.731, 0.883]** |
| Macro-F1 | 0.495 |
| Within one stage | 90.2% |
| Referable sensitivity | **90.5% [82.5%, 96.9%]** |
| Referable specificity | 89.7% [79.4%, 97.8%] |
| Referable AUROC | **0.943** |
| Per-grade recall 0–4 | 0.88 / **0.00** / 0.69 / 0.50 / 0.38 |
| Referable called non-referable / reverse | 6 / 4 |
| Deferral rate | 15.7% |

```
confusion (rows true 0–4, cols predicted)
 30  2  2  0  0
  3  0  2  0  0
  4  1 22  4  1
  1  0  7  9  1
  0  0  2  6  5
```

**The routing test.** The pre-registered hypothesis (ADR-039/040): eyes that pass the quality check, have stage confidence ≥ 0.55 and
P(referable) < 0.136 can go to a **routine rescreening** pile with a referable miss rate around the **2.5% target**; the tolerance for
failing verification was **4.5%**.

| | Result |
|---|---|
| Images routed to routine | 34 of 102 (33.3%) |
| **Referable images routed to routine** | **5 of 63 = 7.9%, exact upper bound 17.6%** |

**The automatic-routing hypothesis failed** on the locked IDRiD test (7.9% > 4.5%). The five misses (descriptive): IDRiD_060 (grade 3),
IDRiD_076, 079, 081, 084 (grade 2); all were **confident stage-0 calls** (score 0.00–0.13, confidence 0.78–0.96); three carry IDRiD DME
grade 2 that our photographic DME rule rated "low".

**What this does NOT mean:** "the model failed". Grading agreement (QWK 0.82) and referable ranking (AUROC 0.94) held up reasonably. It
means the evidence supports **AI-assisted prioritisation with clinician review**, and does **not** support **autonomous routine
disposition** under our own safety criterion. Nothing was changed after this result.

**Why the grade-3 → stage-0 case matters.** It is the clearest example that high confidence can be wrong, and that a single model's
confidence cannot by itself make a "safe to skip the specialist" decision.

---

## Part 31 — DeepDRiD

**[EXPERIMENT on the frozen system, external]** — `results/locked/deepdrid.json`, ADR-034a/035/043/046.

| Item | Value |
|---|---|
| Images / patients | 2,000 regular fundus images, 500 patients (2 views per eye) |
| Removed for leaks (near-copies of training data) | 12 (11 MMRDR, 1 APTOS) → **1,988 locked** |
| Grade "cannot be graded" (DeepDRiD grade 5, stored as None) | 11 → **1,977 graded images** |
| Image QWK [95% CI, bootstrap by patient] | **0.780 [0.753, 0.806]** |
| Macro-F1 / within one stage | 0.512 / 91.2% |
| Referable sensitivity / specificity | **93.0% [90.9, 94.9] / 84.2% [81.5, 86.8]** |
| Referable AUROC | 0.946 |
| Per-grade recall 0–4 | 0.579 / 0.440 / 0.763 / 0.365 / 0.643 |
| Referable called non-referable / reverse | 60 / 177 images |
| Severe under-grading (3–4 → 0–1) | 3 of 463 images |
| Confidence on the 60 missed referable images | 44 had confidence ≥ τ 0.55; 5 ≥ 0.85 |
| Eye level (max-score view) QWK | 0.762 (942 eyes) |
| Image routing at 2.5% | 23.9% routed; **9 / 856 referable missed (upper bound 2.0%)** |
| Patient routing at 2.5% | **7.0%** of patients routed; **0 / 248 referable patients missed (upper bound 1.5%)** |
| Patient states | 285 expedited review, 76 referable, 89 clinician review, 15 retake, 35 routine |
| Quality check vs DeepDRiD "overall quality" | **53.6%** agreement; flags 16.3% of poor, 3.8% of good images |

```
image confusion (rows true 0–4, cols predicted), n = 1,977
523 241 119  16   4
 84  96  36   1   1
  9  48 300  35   1
  1   1 109 128 112
  0   1  19  20  72
```

**Reading it.** Grading generalised with a moderate drop. The model **over-grades** many grade-0 images (241 → 1, 119 → 2), which
lowers specificity and the routine pile. At patient level no referable patient was routed to routine, but only 7% of patients were
routed there at all (either eye blocks routine; 57% of patients went to expedited review). The quality check barely agrees with
DeepDRiD's quality labels.

**Manual replay case `321_r2.jpg`.** Official DeepDRiD: **grade 3 (severe NPDR)**, quality = good (`quality_ok: true` in the locked
manifest). DrishtiQ (locked run): **stage 3**, stage confidence 0.756, DME risk "possible", state expedited review. It is a successful
individual external-domain replay case. It is **not** evidence that every lesion overlay on that image is correct, and the same patient's
`321_r1` was called stage 4.

---

## Part 32 — Dataset lineage

**Simple analogy.** You cannot claim a student never saw the exam if some exam questions came from the question bank they studied.

**Verified facts.** MMRDR's colour fundus images come from OIA-DDR (CLAIMS_LEDGER C14, paper). Our hash audit found **647 of 757** DDR
lesion-segmentation images are near-copies of MMRDR images (`results/audit/ddr/ddr_seg_audit.json`; ADR-014). MMRDR is grader training data.

**Consequences**
- DDR (or anything derived from it) **cannot** be described as an independent external **grading** test.
- DDR-test is acceptable as a *segmentation* check (the lesion models never trained on DDR), but was excluded from any analysis where the
  grader would have seen the images (ADR-014, ADR-021).
- RETFound's pretraining included Kaggle EyePACS (C11), one reason EyePACS was never a test set.
- DeepDRiD was hash-checked against IDRiD, APTOS, MMRDR and DDR; 12 near-copies were removed before locking.

---

## Part 33 — Lesion counts

**"35 microaneurysms" in the app means:** the MA model's mask, after thresholding, has 35 separate connected regions. It does **not**
mean 35 clinically confirmed microaneurysms. One real lesion can split into two regions; two can merge; a vessel crossing can be counted.

**Object-level validation** (how a count would be validated):

```
EXPERT MASK → connected lesion objects          PREDICTED MASK → predicted objects
                         └──────── match (e.g. overlap IoU ≥ 0.1, one-to-one) ────────┘
   true positives (matched)   false positives (predicted, unmatched)   false negatives (expert, unmatched)
```

- **Object sensitivity** = TP / (TP + FN): of the real lesions, how many were found.
- **Object precision** = TP / (TP + FP): of the predicted lesions, how many were real.
- **Dice** and **AUPR**: pixel-level overlap and ranking (Part 20).

**Why count agreement alone is insufficient:** a model with 10 false positives and 10 misses can report the "right" count.

What we have: component recall/precision for the MA study (full512: 0.255 / 0.438; `MA_specialist_scorecard.csv`) and false-positive
regions on grade-0 images (Part 24). We do **not** have expert object-level validation of the app's counts. They are model outputs.

---

## Part 34 — Rural-first design thinking

We designed from failure modes backwards. Labels show what exists today.

| Failure | Response | Status |
|---|---|---|
| 1. Patient leaves with a bad image | capture-time quality check; retake reasons shown immediately in the results step | **[IMPLEMENTED]** heuristic; weak on DeepDRiD (53.6% agreement) |
| 2. Tiny lesions disappear during resizing | measure the loss (Part 8); investigate global + high-resolution local analysis | evidence [EXPERIMENT]; architecture **[PROPOSED]** |
| 3. Local patches create false positives | keep global/anatomical context; evaluate patch selection for lesion retention | **[PROPOSED]** (motivated by the patch experiment) |
| 4. One model can be confidently wrong | calibrated confidence, deferral, separate lesion evidence, human review | **[IMPLEMENTED]**; locked test shows it is not sufficient for autonomy |
| 5. Specialist receives unsorted cases | worklist ordered expedited → clinician review → referable → retake → routine | **[IMPLEMENTED]** |
| 6. One eye analysed, fellow eye missing | patient-level aggregation; missing eye → "incomplete screening", never routine | **[IMPLEMENTED]** |
| 7. AI confidence mistaken for truth | wording rules (no "normal / cleared"), uncertainty shown, clinician authority | **[IMPLEMENTED]** in UI text and tests (`tests/test_wording.py`) |

This is the intellectual identity of the project: the system is shaped by where screening goes wrong, not by a leaderboard.

---

## Part 35 — What makes DrishtiQ different

Not "AI-powered, real-time, high accuracy, explainable, user-friendly". These are the substantive differences:

- **Data-integrity-first development** [IMPLEMENTED]: duplicate/conflict quarantine, hash-based leak checks across all datasets.
- **Pre-registered decisions** [IMPLEMENTED]: every model swap, threshold and routing claim had a rule written down before its result (ADR log).
- **Locked evaluation, including negative results** [IMPLEMENTED]: frozen `rc-1`, run once, failures reported on the About page.
- **Capture-aware workflow** [IMPLEMENTED, limited]: retake reasons before the patient leaves.
- **Separate global grading and local evidence** [IMPLEMENTED]: grader and lesion models are independent; we do not pretend the lesions computed the grade.
- **Honest uncertainty** [IMPLEMENTED]: calibrated P(referable) and stage confidence, deferral, "confidence is not correctness".
- **Patient-level workflow** [IMPLEMENTED]: worse eye decides, missing eye → incomplete, repeat visits never downgrade a signed referral.
- **Specialist-attention prioritisation** [IMPLEMENTED]: worklist order.
- **Resolution-aware architecture thinking** [EXPERIMENT evidence → PROPOSED design].
- **Capability-aware interpretation** [IMPLEMENTED in explanation text]: the "Limits" sentences state what the system cannot see (e.g. new vessels).

---

## Part 36 — What we must never claim

| ❌ Never say | ✓ Say instead |
|---|---|
| "DrishtiQ diagnoses diabetic retinopathy." | "DrishtiQ assists DR screening; a clinician decides." |
| "99% confidence means 99% clinically certain." | "It is a calibrated estimate on development data; our locked test had a confident grade-3 → stage-0 error." |
| "No segmented lesions means no PDR." | "We cannot detect new vessels or vitreous haemorrhage." |
| "Grad-CAM proves where the disease is." | "Grad-CAM shows where the grading model's evidence came from." |
| "Yellow deposits near the fovea diagnose DME." | "Hard exudates near the fovea are a photographic risk sign; DME needs OCT/clinical exam." |
| "Indian data means validated for rural India." | "Trained mostly on Indian and Chinese public datasets; not validated prospectively in any rural programme." |
| "DDR is an independent external grading test." | "DDR shares lineage with our MMRDR training data." |
| "Our lesion counts are clinically verified." | "Counts are connected regions in a model mask." |
| "Automatic routine routing is safe." | "Our locked IDRiD test rejected autonomous routine routing (5/63 missed)." |
| "We beat RETFound." / "RETFound is worse." | "RETFound's gain was not statistically supported under our rule." |
| "Messidor-2 validated." | "Messidor-2 has not been evaluated." |
| "It works fully offline on any laptop." | Do not advertise this (team decision). The CPU path is verified only on our laptop with `RS_DEVICE=cpu`. |
| "Clinician corrections update the report and routing." | "Reviews are stored and printed; routing of that visit still uses the AI stage." |

---

## Part 37 — What is missing for a real clinical system

- **Multi-site external validation** (several clinics, cameras, populations), including Messidor-2 and prospective data.
- **Patient-level independence** in every dataset (patient IDs).
- **Camera/site generalisation** analysis.
- **Validated gradability** (task-aware) and **OOD detection** (our OOD score was abandoned: AUROC 0.62 for dataset shift).
- **Complete advanced-lesion vocabulary** (venous beading, IRMA, NV, vitreous haemorrhage).
- **Better MA localisation** (current MA Dice 0.275 on 10 images; DDR-test AUPR 0.053).
- **Clinician-approved labels** and adjudication; a native-speaker clinical review of the Hindi text.
- **Prospective validation**, then **silent/shadow deployment** next to standard care.
- **Workflow and usability studies** with real health workers and ophthalmologists.
- **Governance:** clinical safety case, incident reporting, audit trail.
- **Privacy and security:** authentication (none exists), encryption at rest and in transit, access control, retention and deletion policies.
- **Regulatory requirements** for software as a medical device.
- **Monitoring** for drift and performance after deployment.
- **Correction propagation:** clinician reviews should drive the final report and routing.

**This is a hackathon research prototype, not a medical device.**

---

## Part 38 — Future clinical-grade architecture (proposed)

**[PROPOSED, NOT IMPLEMENTED]**

```
PATIENT → FUNDUS ACQUISITION → MODALITY VALIDATION → TASK-AWARE GRADABILITY → OOD / DOMAIN CHECK → ANATOMY
→ GLOBAL + HIGH-RES LOCAL ANALYSIS → DR GRADING + LESION / ADVANCED-SIGN ANALYSIS → CAPABILITY-AWARE CONSISTENCY
→ CALIBRATED RELIABILITY → ABSTAIN / RETAKE / REVIEW WHEN NEEDED → BILATERAL PATIENT ASSESSMENT
→ SPECIALIST PRIORITISATION → CLINICIAN SIGN-OFF → PATIENT REPORT / REFERRAL
```

| Component | Failure it solves | How we would test it |
|---|---|---|
| Modality validation | non-fundus or wrong-modality images analysed | curated non-fundus / OCT / external-eye images; must be rejected (the planned R2 test) |
| Task-aware gradability | an image adequate for big lesions is used to rule out tiny ones | expert gradability labels per task; agreement and miss rates per task |
| OOD / domain check | silent failure on unfamiliar cameras/populations | known-shift tests (site, camera); AUROC and, crucially, error reduction among routed cases |
| Anatomy | lesions confused with the disc/vessels; macula unknown | landmark error vs expert markups on locked images |
| Global + high-res local | tiny lesions lost by resizing | lesion retention of the patch selector; MA object sensitivity at fixed false positives |
| Advanced-sign analysis | PDR / severe NPDR missed | labelled NV/VH/IRMA/beading sets; Grade-4 recall |
| Capability-aware consistency | grade and lesion evidence contradict each other silently | pre-registered disagreement rules; relative risk and miss reduction (our Step-4 test, with a better segmenter) |
| Calibrated reliability | confident errors | calibration and confident-error rate on locked external data |
| Abstain / retake / review | forced answers on uncertain cases | coverage vs miss-rate curves; prospective retake success rate |
| Bilateral assessment | one-eye decisions | patient-level metrics with patient-bootstrap CIs (as on DeepDRiD) |
| Specialist prioritisation | urgent cases wait | time-to-specialist and workload studies |
| Clinician sign-off | AI output treated as final | audit of overrides; report generated from the signed decision |
| Patient report / referral | patient does not understand or act | comprehension testing (incl. Hindi) and referral completion |

---

## Part 39 — Complete scorecard

| Section | Metric | Dataset | Value | n | What it means | Verdict | Caveat |
|---|---|---|---|---|---|---|---|
| Grading — dev | QWK | IDRiD-val | 0.893 [0.846, 0.929] | 101 | strong ordinal agreement | good | candidates compared here |
| Grading — dev | QWK | APTOS-val | 0.918 [0.896, 0.938] | 518 | strong | good | single-grader labels |
| Grading — dev | macro-F1 | IDRiD-val / APTOS-val | 0.545 / 0.628 | 101 / 518 | rare classes weak | weak | |
| Grading — dev | Grade-1 recall | IDRiD-val / APTOS-val | 0.20 / 0.38 | 5 / 50 | mild disease missed or over-graded | weak | tiny n on IDRiD |
| Grading — dev | Grade-4 recall | IDRiD-val / APTOS-val | 0.33 / 0.56 | 12 / 39 | PDR under-called as 3 | weak | 3 and 4 both urgent |
| Grading — dev | referable sens / spec | IDRiD-val | 93.7% / 100% | 101 | | good | |
| Grading — dev | referable sens / spec | APTOS-val | 95.0% / 90.5% | 518 | | good | |
| Grading — locked | QWK | IDRiD clean test | 0.816 [0.731, 0.883] | 102 | drop from dev | moderate | run once |
| Grading — locked | referable sens / spec | IDRiD clean test | 90.5% / 89.7% | 102 | | moderate | wide CIs |
| Grading — locked | AUROC | IDRiD clean test | 0.943 | 102 | good ranking | good | not individual safety |
| Grading — locked | Grade-1 recall | IDRiD clean test | 0 / 5 | 5 | | weak | tiny n |
| Grading — external | QWK | DeepDRiD | 0.780 [0.753, 0.806] | 1,977 | moderate generalisation | moderate | 2 views per eye |
| Grading — external | referable sens / spec | DeepDRiD | 93.0% / 84.2% | 1,977 | over-grades grade 0 | moderate | |
| Grading — external | AUROC | DeepDRiD | 0.946 | 1,977 | | good | |
| Segmentation | Dice MA / HE / EX / SE | IDRiD-val | 0.275 / 0.422 / 0.559 / 0.447 | 10/10/10/5 | | weak–moderate | not independent of selection |
| Segmentation | AUPR MA / HE / EX / SE | DDR-test | 0.053 / 0.163 / 0.352 / 0.105 | 225 | | weak | other domain |
| RETFound | ΔQWK vs ConvNeXt (probes) | IDRiD-val / APTOS-val | +0.030 [−0.065, 0.129] / +0.020 [−0.018, 0.061] | 101 / 518 | not significant | uncertain | frozen probes only |
| Quality | agreement with quality labels | DeepDRiD | 53.6% (flags 16.3% of poor) | 1,988 | weak | weak | heuristic |
| Calibration | ECE P(referable) after | IDRiD-val / APTOS-val | 0.083 / 0.027 | 101 / 518 | | mixed | worse on IDRiD after calibration |
| Calibration | deferral rate | IDRiD-val / APTOS-val / IDRiD test / DeepDRiD | 8.9% / 6.4% / 15.7% / 14.3% | | | — | |
| Routing | referable routed to routine, 2.5% | IDRiD-val / APTOS-val | 2/63 / 1/201 | | within target on dev | good (dev) | thresholds from hold-out |
| Routing | referable routed to routine, 2.5% | **IDRiD clean test** | **5/63 = 7.9% (UB 17.6%)** | 102 | **hypothesis rejected** | **failed** | incl. one grade 3 |
| Routing | referable routed to routine | DeepDRiD images / patients | 9/856 (UB 2.0%) / 0/248 (UB 1.5%) | 1,988 / 500 | within target | good but small pile (7% patients) | |
| Explanations | faithfulness (cited vs random) | IDRiD-val / APTOS-val | p = 4.5e-6 / 4.3e-17 | 59 / 221 | explanations point at score-driving regions | supported (dev) | |
| Speed | analysis per image GPU / CPU | IDRiD dev-train | 1.04 s / 1.42 s | 10 | | — | RTX 3050 laptop |

---

## Part 40 — Complete model inventory

**Loaded by the frozen application (`rc-1`)** [IMPLEMENTED]

| Component | Architecture | Parameters | Checkpoint size | Input | Training data | Purpose |
|---|---|---|---|---|---|---|
| DR grader | ConvNeXt-Tiny (`convnext_tiny.fb_in1k`), regression head | 27,820,897 | 111,363,403 B | 384 × 384 FOV crop | IDRiD 303 + APTOS 2,929 + MMRDR 10,831 | stage 0–4, Grad-CAM |
| HE / EX / SE segmenter | SegFormer-B0 (MiT-B0), 4 channels | 3,451,748 | 13,884,449 B | 512 letterbox | 40 IDRiD segmentation images | lesion masks |
| MA segmenter | U-Net, ResNet18 encoder | 12,461,009 | 49,961,003 B | 512 letterbox | 40 IDRiD segmentation images | MA mask |
| Post-processing | pp_v2 thresholds | — | `configs/postprocess/pp_v2.json` | — | IDRiD 50 dev seg images (OOF) | clean masks |
| Calibration | Platt + isotonic + τ | — | `configs/calibration/app_grader.json` | score | inner hold-out 2,813 | P(referable), confidence, deferral |
| Routing | rules + thresholds | — | `configs/routing/routing_v1.json` | outputs | inner hold-out 2,813 | eye/patient states |
| Optic disc | brightness heuristic | — | code | image | — | landmark |
| Fovea | anatomical prior + dark-spot search | — | `configs/landmarks/fovea_v1.json` | image | IDRiD dev-train localisation labels | landmark |
| DME proxy | hard exudate within 1 DD of fovea, regions < 40 px ignored | — | `configs/landmarks/dme_rule_v1.json` | masks + landmarks | IDRiD dev-train | "swelling risk" (val high-risk sens 86%, PPV 81%) |
| Quality check | heuristics (+ fitted corner threshold) | — | `configs/quality/quality_v1.json` | image | 900 training + 64 synthetic images | retake |

**Experimental models (not loaded)** — see Part 18: early frozen ConvNeXt heads, phase-1 fine-tunes (ConvNeXt-T, EfficientNet-B3), RETFound
probes, ConvNeXt-T probes, CE-384 and reg-512 A2 screens, seed-23 replica, referable-head (`regbin`) variant, prior-study ResNet50 /
EfficientNet-B0 / Swin-T, prior-study U-Net / U-Net++ / DeepLabV3+ segmenters, A3 fold models (incomplete).

---

## Part 41 — Complete dataset inventory

| Dataset | Total images | Used | Training | Validation | Test | Annotation | Domain | Role | Leakage concerns |
|---|---|---|---|---|---|---|---|---|---|
| IDRiD grading | 516 files / 510 distinct | 506 | 303 | 101 | 102 (locked) | ICDR + DME | India, one camera | train/val/locked test | patient IDs unknown; 10 conflicting/duplicate excluded |
| IDRiD segmentation | 81 | 50 dev (40 train / 10 val) | 40 | 10 | 27 official test **reserved, not evaluated** | pixel masks | India | lesion models | 4 cross-task candidates excluded |
| APTOS 2019 | 3,662 | 3,447 | 2,929 | 518 | — | ICDR, one grader | India | grading train/val | 8 IDRiD matches dropped; label noise |
| MMRDR-CFP | 11,118 | 10,831 | 10,831 | — | — | ICDR + lesion presence | China | grading train | derived from OIA-DDR |
| DDR lesion set | 757 | 225 test (eval) | — | — | 225 (seg check) | pixel masks | NOT VERIFIED | segmentation check | 647/757 near-copies of MMRDR |
| DeepDRiD regular | 2,000 | 1,988 (1,977 graded) | — | — | 1,988 (locked, external) | ICDR per eye, quality | NOT VERIFIED | external test | 12 near-copies removed |
| Messidor-2 | — | 0 | — | — | planned | adjudicated | — | **not evaluated** | — |
| EyePACS | — | 0 | — | — | — | — | — | cancelled | in RETFound pretraining |

---

## Part 42 — Complete experiment timeline

Dates from git history (79 commits, 28–31 Oct 2026) and the decision log.

1. **Before / at the start (28 Oct):** IDRiD audit → clean protocol (ADR-001). Prior model-selection study: 4 backbones, resolutions,
   objectives; 4 segmentation architectures; MA follow-up. → Lesson: ConvNeXt-T frozen is a fair baseline; Grade-1 and MA are the hard parts.
2. **28 Oct, v0 prototype:** frozen ConvNeXt-T @224 (6 heads) + SegFormer + MA U-Net in a working app (ADR-009). → Discovered its heads saw
   IDRiD-val → built a clean comparator (ADR-010, QWK 0.795 / 0.720).
3. **28 Oct, pp_v2:** lesion post-processing chosen with a false-positive constraint (ADR-011).
4. **28 Oct, phase-1 fine-tunes (IDRiD only):** ConvNeXt-T vs EfficientNet-B3 → ConvNeXt better; IDRiD-only training fails on APTOS → need more data.
5. **28 Oct, A1 probes:** ConvNeXt vs RETFound frozen → RETFound not adopted (ADR-012).
6. **28–29 Oct, A2:** mixed-pool full fine-tuning; reg384 chosen on the inner hold-out (ADR-015); passes ADR-013 → **app grader**.
7. **29 Oct, B5/B6:** calibration, deferral, worklist metrics (ADR-019/020).
8. **29–30 Oct, A3 segmentation:** started; stalled after a GPU driver fault; **cancelled** (ADR-041). Seed 23 trained.
9. **30 Oct, Approach V2:** routing hypothesis pre-registered (ADR-039); Step 2 dev coverage; Step 3 decision layer (ADR-040); Step 4
   experiments: disagreement, OOD, referable head **abandoned**; ensemble **not testable**; faithfulness **supported**; robustness **reported** (ADR-042).
10. **30 Oct, rc-1 freeze** (ADR-045) → **locked evaluation** (ADR-046): IDRiD test routing **failed**; DeepDRiD grading moderate, patient routing within target but small.
11. **31 Oct, UI v3** (`ui-v3`): DrishtiQ interface and landing page; no model changes.

---

## Documentation conflicts found while writing this handbook

| Document | Statement | Current evidence | Use |
|---|---|---|---|
| `docs/MODEL_CARD.md` | Messidor-2 "evaluated once, after rc-1" | Messidor-2 not available; not evaluated (ADR-046, About page) | **not evaluated** |
| `docs/MODEL_CARD.md` | "non-fundus images are never given a confident stage (R2)" | R2 was cancelled, never run (`queue/jobs.yaml`) | **unverified** |
| `docs/MODEL_CARD.md` | "Grad-CAM can focus on the optic disc … (R3)" | R3 never run | plausible, **unverified** |
| `docs/MODEL_CARD.md` | "validated only on datasets from India so far" | DeepDRiD locked evaluation done; MMRDR (Chinese) in training | outdated |
| `docs/MODEL_CARD.md` | lesion segmenter "v0.1 … or A3" | A3 cancelled; app uses v0.1 | v0.1 only |
| `docs/MODEL_CARD.md` | "Mild DR is under-called … because microaneurysms are a few pixels wide" | cause is a hypothesis (CLAIMS_LEDGER H02); APTOS mostly over-grades Grade 1 | hypothesis |
| `docs/MODEL_CARD.md` | code licence "still to be decided" | README states MIT | check with the team |
| `ADR-015` | best regression epoch "14" | 0-based index; it is the 15th of 15 epochs | 15th epoch |
| `README.md` | "The app works fully offline" | team decision not to advertise offline use; CPU path verified only on our laptop | do not advertise |

---

## Verification table — 30 key claims

| # | Claim | Verified? | Evidence source |
|---|---|---|---|
| 1 | Active grader is timm `convnext_tiny.fb_in1k`, regression head, 384 px | ✓ | checkpoint JSON; `configs/app/app.json` |
| 2 | 27,820,897 parameters, all trainable | ✓ | state dict + timm count |
| 3 | Checkpoint 111,363,403 bytes, SHA-256 acf53697… | ✓ | disk; ADR-045 |
| 4 | Cut points 0.52702448 / 1.40838036 / 2.63552623 / 3.46447762 | ✓ | checkpoint JSON |
| 5 | Pool 14,063 = 303 + 2,929 + 10,831; inner hold-out 2,813 | ✓ | checkpoint JSON; calibration file |
| 6 | Smooth-L1, AdamW, lr 2e-4, wd 0.05, effective batch 32, clip 2, AMP, 1-epoch warm-up + cosine, 15 epochs, patience 4, seed 17 | ✓ | `finetune_mixed.py`; checkpoint JSON |
| 7 | Best checkpoint = 15th (last) epoch | ✓ | `best_epoch: 14` (0-based), history length 15 |
| 8 | Training and runtime preprocessing identical | ✓ | code comparison |
| 9 | IDRiD 516 records, 510 distinct, clean 404/102, 10 excluded | ✓ | IDRiD policy and audit docs |
| 10 | 35.5% of MA components vanish at width 224; 5.6% at 384 | ✓ | `IDRiD_RESOLUTION_FINDINGS.md` |
| 11 | IDRiD_21: 80 MA components, median 2.85 px at 384, 7 below 1 px | ✓ (computed for this handbook) | IDRiD_21_MA.tif + `fov_box` |
| 12 | Frozen ConvNeXt-T @224 baseline macro-F1 0.506, QWK 0.774, Grade-1 recall 16.7% | ✓ | `grading_scorecard.csv`, per-class file |
| 13 | Dev IDRiD-val QWK 0.893, macro-F1 0.545, accuracy 0.673 | ✓ | registry 20261029-083502; predictions |
| 14 | Dev APTOS-val QWK 0.918, macro-F1 0.628, accuracy 0.811 | ✓ | registry 20261029-083933; predictions |
| 15 | Per-grade recall IDRiD .939/.200/.697/.500/.333; APTOS .993/.380/.759/.400/.564 | ✓ | registry; confusion matrices |
| 16 | Grade-1: IDRiD 1/5 (4 → 0); APTOS 19/50 (1 → 0, 27 → 2, 2 → 3, 1 → 4) | ✓ | prediction files |
| 17 | Grade-4: IDRiD 4/12; APTOS 22/39 | ✓ | prediction files |
| 18 | RETFound ViT-L/16, 303,301,632 encoder parameters, 224 px | ✓ | timm count; ADR-012 |
| 19 | RETFound vs ConvNeXt probes QWK 0.7693/0.7398 (IDRiD), 0.8817/0.8616 (APTOS); macro-F1 0.4519/0.4041, 0.6887/0.6029 | ✓ | registry |
| 20 | RETFound ΔQWK CIs include 0; rule fails | ✓ | ADR-012 |
| 21 | ADR-013 swap: ΔQWK +0.098 [0.036, 0.171], +0.198 [0.152, 0.247] | ✓ | `queue/decisions/a2_swap.json` via KEY_NUMBERS |
| 22 | Segmentation IDRiD-val Dice MA .275, HE .422, EX .559, SE .447; 10/10/10/5 images | ✓ | registry 20261028-223254 |
| 23 | MA patch experiment Dice 0.287 (full) vs 0.169 (patch), recall 0.27 vs 0.73 | ✓ | `MA_specialist_scorecard.csv` |
| 24 | SegFormer-B0 3,451,748 params; MA U-Net 12,461,009 params | ✓ | timm/smp count; experiment configs |
| 25 | Calibration: Platt 3.1194 / −4.5339; τ = 0.55; routing threshold 0.13603 | ✓ | calibration and routing configs |
| 26 | Locked IDRiD test: QWK 0.816, sens 90.5%, AUROC 0.943, 5/63 routed to routine (7.9%, UB 17.6%) | ✓ | `results/locked/idrid_test.json` |
| 27 | Locked miss IDRiD_060: grade 3 → stage 0, confidence 0.956 | ✓ | `idrid_test_images.jsonl` (ADR-046) |
| 28 | DeepDRiD: 1,988 locked, 1,977 graded, QWK 0.780, sens 93.0%, spec 84.2%, AUROC 0.946 | ✓ | `results/locked/deepdrid.json` |
| 29 | DeepDRiD patient routing 0/248 missed at 7.0% coverage; quality agreement 53.6% | ✓ | `results/locked/deepdrid.json` |
| 30 | 321_r2: DeepDRiD grade 3, good quality → DrishtiQ stage 3 | ✓ | locked manifest + `deepdrid_images.jsonl` |

---

## The 15 things every DrishtiQ team member must know

1. **DrishtiQ assists DR screening; it does not diagnose.** The ophthalmologist is the final authority; it is a research prototype, not a medical device.
2. **The problem is specialist attention, not compute.** We catch retakes early and order the worklist by urgency.
3. **The grader is a fully fine-tuned ConvNeXt-Tiny (27.8 M parameters) that outputs one severity number**, cut into stages 0–4 by four thresholds fitted on held-out data.
4. **It was trained on 14,063 images** (IDRiD 303, APTOS 2,929, MMRDR 10,831), with 2,813 held out inside training for every threshold and calibration.
5. **We cleaned the data first:** IDRiD had identical photos with different grades; we quarantined them (404/102 clean split) instead of inventing labels.
6. **Every model change followed a rule written before the result.** ConvNeXt replaced the baseline by such a rule; RETFound did not pass it. That is "not proven better", not "worse".
7. **Development results:** QWK 0.893 (IDRiD-val) and 0.918 (APTOS-val), referable sensitivity 94–95%.
8. **Weakest classes:** Grade 1 (IDRiD 1/5, APTOS 19/50) and Grade 4 (4/12, 22/39). We cannot detect new vessels, so we cannot rule out PDR.
9. **Resolution is a known bottleneck:** at 384 px a microaneurysm is a few pixels; 5.6% of annotated MA components vanish entirely.
10. **Lesion maps come from separate models** (SegFormer-B0, MA U-Net), validated on only 10 images; counts are regions, not confirmed lesions.
11. **Grad-CAM shows where the grader looked**, not where disease is.
12. **Confidence is not correctness:** a grade-3 eye was called stage 0 with 0.956 confidence in our locked test.
13. **Locked IDRiD test:** QWK 0.816, sensitivity 90.5%, AUROC 0.943 — but **automatic routine routing failed** (5/63 referable missed). We report that openly.
14. **DeepDRiD (external, 1,988 images):** QWK 0.780, sensitivity 93.0%, no referable patient routed to routine, but only 7% routed there; quality check agreement only 53.6%.
15. **Next steps:** multi-site prospective validation, better small-lesion analysis (global + local, proposed), advanced-sign detection, task-aware gradability, and clinician corrections that drive the final report.
