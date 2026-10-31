# RetinaScreen approach V2 (frozen 2026-10-30)

**Core hypothesis:** the existing DR system can safely identify a meaningful subset of screening cases that do not need immediate specialist review, while escalating everything uncertain. It is tested by a pre-registered experiment (ADR-039) before any of it is built.

## Architecture (6 blocks)

| # | Block | Role |
|---|---|---|
| 1 | Capture check | Retake now if the image is unusable |
| 2 | Whole-retina assessment | Severity 0–4 + calibrated referral risk |
| 3 | Lesion evidence | MA / HE / EX / SE located on anatomy (disc, fovea, quadrants). **Escalate-only** |
| 4 | Reliability decision | ROUTINE_RESCREEN_ELIGIBLE only if every available safety signal agrees; otherwise CLINICIAN_REVIEW, with the reason |
| 5 | Patient routing | Both eyes combined |
| 6 | Clinician worklist + sign-off | Evidence; Grad-CAM in the physician view (a problem-statement requirement); final decision; report |

## Design rules

- **The AI never clears or calls an eye normal or healthy.**
  - Internal state: `ROUTINE_RESCREEN_ELIGIBLE`.
  - Clinician text: "No referable diabetic retinopathy detected by AI in gradable images of both eyes."
  - Patient text: "This photo check did not find diabetic eye damage that needs a specialist now. It is not a full eye examination. Come back for your next check, or sooner if your vision changes."
- **Lesion evidence only escalates.** The absence of detected lesions never lowers a decision; new vessels, IRMA and venous beading are outside the lesion vocabulary.
- **The four reliability signals stay distinct:**
  - poor quality → retake
  - out of distribution → review
  - in-domain uncertainty → review
  - global/local disagreement → review, with the contradiction stated
- **Conditional components**, kept out of the production decision path until their own experiment passes: OOD score, separate referable head, seed ensemble, global/local disagreement, lesion → grade fusion.
- **Not implemented:**
  - lesion-derived grading via hard-coded rules
  - grade changes driven by disagreement
  - "healthy eye" claims
  - a fundus-only DME diagnosis
  - hierarchical transformers, attention fusion or learned ROI selection
  - LLM-written explanations
  - a clinical questionnaire

## Status

- **Step 1:** pre-registration (ADR-039).
- **Step 2:** baseline experiment on the pinned grader (results in `results/coverage/`).
- **Step 3:** waits for an explicit GO.
