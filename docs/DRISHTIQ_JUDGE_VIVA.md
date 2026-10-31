# DrishtiQ — Judge Viva Preparation

Practice questions with a **short answer** (say this first), a **deep answer** (if the judge digs) and, where useful, **do not say**.
Every number is traced in the [team handbook](DRISHTIQ_TEAM_TECHNICAL_HANDBOOK.md) (part numbers in brackets).

Golden rules: answer the question asked; give the number and its dataset; say "development" or "locked" every time; say "we don't
know" when we don't.

---

## A. Basic medical questions

**1. What is diabetic retinopathy?**
- Short: damage to the small blood vessels of the retina caused by long-term diabetes; it can lead to blindness if untreated.
- Deep: vessels leak (exudates, haemorrhages), bulge (microaneurysms) and close off; the retina then grows fragile new vessels
  (proliferative DR) that can bleed. Graded 0–4 on the ICDR scale [Part 2].
- Do not say: anything that sounds like we diagnose it.

**2. Why screen people who can see well?**
- Short: early DR has no symptoms; treatment works best before vision is lost.
- Deep: damage is usually away from the macula at first; by the time vision drops, disease may be advanced.

**3. What are microaneurysms, haemorrhages and exudates?**
- Short: tiny capillary bulges; small bleeds; yellow fat/protein deposits (hard) or fluffy nerve-fibre swellings (soft / cotton-wool).
- Deep: these are the four lesions our segmentation models mark; we do not detect venous beading, IRMA, new vessels or vitreous haemorrhage.

**4. What separates stage 3 from stage 4?**
- Short: stage 4 (proliferative) needs new vessels or vitreous/preretinal bleeding; stage 3 is severe damage without them (4-2-1 rule).
- Deep: 4-2-1 = >20 haemorrhages in each of 4 quadrants, beading in ≥ 2, or IRMA in ≥ 1 [Part 2].

**5. Can you detect DME?**
- Short: no. We flag a photographic risk sign — hard exudates within one disc diameter of the fovea.
- Deep: true DME is retinal thickening, measured with OCT. Our proxy reached high-risk sensitivity 86% and PPV 81% against IDRiD's
  photographic DME labels on IDRiD-val (`dme_rule_v1.json`); on the locked test, three of the five routing misses had IDRiD DME grade 2
  that our rule called low [Part 30].
- Do not say: "we diagnose macular edema".

**6. Why are DR stage and DME different?**
- Short: DME can occur at any stage; a moderate eye can have DME and a proliferative eye may not.

---

## B. Dataset questions

**7. What data did you train on?**
- Short: 14,063 images — IDRiD 303, APTOS 2,929, MMRDR 10,831 — with 2,813 held out inside training.
- Deep: dataset-balanced sampling with 1/√ class weights; validation and locked images never entered the pool [Part 14].

**8. How do you know datasets don't overlap?**
- Short: we hash-checked every set against every other with a calibrated structure hash and removed near-copies.
- Deep: APTOS dropped 8 IDRiD matches; MMRDR dropped 46 near-copies of validation/locked images; DeepDRiD dropped 12 near-copies of
  training images before locking [Part 7, Part 32].
- Do not say: "there is zero patient overlap" — patient IDs are unavailable.

**9. What did you find in IDRiD?**
- Short: 516 grading files but 510 distinct photos; identical images with conflicting grades, one across train/test (grade 0 vs 3).
- Deep: 6 duplicate groups, 4 conflicting; we quarantined 8 and dropped 2 redundant copies → 404/102 clean split [Part 7].

**10. Why not just fix the conflicting labels?**
- Short: we are not the graders; picking a label would invent medical ground truth.

**11. Is IDRiD patient-independent now?**
- Short: no one can verify that — IDRiD has no patient IDs. We removed exact duplicates, not fellow-eye or repeat-visit photos.

**12. Why is DeepDRiD useful?**
- Short: we never trained or tuned on it, it has two photos per eye, quality labels and 500 patients — so we could test patient-level routing.
- Deep: 1,988 locked images after leak removal; QWK 0.780, referable sensitivity 93.0%; patient routing missed 0 of 248 referable
  patients, but only 7% of patients were routed to routine [Part 31].

**13. Can DDR be your external grading test?**
- Short: no. MMRDR (our training data) is derived from OIA-DDR, and 647 of 757 DDR lesion images are near-copies of MMRDR images.

**14. Have you tested on Messidor-2?**
- Short: no. It was planned as a locked test but is not available to us; we have not evaluated it.

**15. Is it validated for rural India?**
- Short: no. Training data are public Indian and Chinese datasets; no prospective or rural-programme validation exists.

---

## C. Deep-learning questions

**16. Why ConvNeXt-Tiny?**
- Short: it led a four-backbone comparison, beat EfficientNet-B3 in every matched fine-tune, passed our pre-registered swap rule, and runs on a 4 GB GPU.
- Deep: prior study frozen 224 px: ConvNeXt-T macro-F1 0.506 / QWK 0.774 vs EfficientNet-B0 0.489 / 0.714, Swin-T 0.485 / 0.720,
  ResNet50 0.458 / 0.684. Fine-tuned on the mixed pool it beat the frozen comparator by ΔQWK +0.098 [+0.036, +0.171] (IDRiD-val) and
  +0.198 [+0.152, +0.247] (APTOS-val) [Part 16].
- Do not say: "ConvNeXt is the best model for DR".

**17. Why not ResNet?**
- Short: in our prior comparison ResNet50 had the lowest frozen scores (macro-F1 0.458, QWK 0.684).

**18. Why not EfficientNet?**
- Short: EfficientNet-B0 scored lower in the prior study; EfficientNet-B3 fine-tuned on IDRiD was worse than ConvNeXt-T in every matched pair and had unstable BatchNorm statistics.

**19. Why not RETFound?**
- Short: frozen RETFound features gave small gains, but the confidence intervals included zero, so our pre-registered rule did not adopt it.
- Deep: ΔQWK +0.030 [−0.065, 0.129] IDRiD-val, +0.020 [−0.018, 0.061] APTOS-val; macro-F1 on APTOS was significantly higher but was not
  the pre-registered metric. RETFound is a 303 M-parameter ViT-L; full fine-tuning does not fit our 4 GB GPU [Part 17].
- Do not say: "RETFound is worse" — we did not show that.

**20. Is the model frozen or fine-tuned?**
- Short: the active grader is fully fine-tuned; the frozen ConvNeXt was our baseline.

**21. Why regression instead of classification?**
- Short: stages are ordered; one severity number keeps "3 is closer to 2 than to 0".
- Deep: Smooth-L1 on the grade, then four cut points fitted to maximise QWK on the hold-out (0.527 / 1.408 / 2.636 / 3.464). Regression
  @384 reached inner QWK 0.929 vs cross-entropy 0.918 [Part 12].

**22. Then what are the probabilities in your API?**
- Short: for a regression model they are one-hot — not real probabilities. The real one is the calibrated P(referable) from Platt scaling.

**23. What are your training settings?**
- Short: AdamW, lr 2e-4 with layer-wise multipliers, weight decay 0.05, effective batch 32, clip 2, AMP, warm-up + cosine, up to 15 epochs, patience 4, seed 17.
- Deep: best checkpoint was the 15th (last) epoch; about 92 minutes on an RTX 3050 laptop GPU [Part 15].

**24. Did you overfit to validation?**
- Short: we limited it — the candidate was fixed on the inner hold-out before validation, and every swap used a rule written in advance.
- Deep: development sets were still used to *compare* candidates, so their numbers are optimistic; that is why we froze and ran a locked test.

---

## D. Architecture questions

**25. Why 384 px?**
- Short: compute. 512 px gave no inner-hold-out gain (0.928 vs 0.929) at 1.8× the training time.
- Deep: we know 384 loses detail: 5.6% of annotated MA components vanish at 384 [Part 8].

**26. Why not 1024?**
- Short: it would preserve microaneurysms (only 0.06% vanish) but needs far more memory and time than a 4 GB GPU allows for the whole image; our proposal is selected high-resolution regions instead [Part 26].

**27. Why do you need segmentation if you have a grader?**
- Short: to show *evidence* a clinician can check — where the lesions are — separate from the grade.

**28. Why keep segmentation separate from grading?**
- Short: few images link the two tasks, and we had no controlled evidence fusion helps (ADR-006). The planned fusion experiment was not run.

**29. Why not derive the grade from lesion counts?**
- Short: counts cannot represent new vessels, beading or IRMA, and our lesion models are weak (MA Dice 0.275); stage 4 cannot be counted.

**30. What happens when the lesion model and the grader disagree?**
- Short: we show both, and the explanation raises a "check" (e.g. "Stage 0 but 13 spots found; a doctor should look").
- Deep: a pre-registered disagreement flag for routing was tested and abandoned — the current segmenter finds many spots on grade-0
  images, so the flag did not separate risk (RR CI [0.34, 106]) [Part 34, Step 4].

---

## E. Evaluation questions

**31. Why QWK?**
- Short: grading is ordinal; QWK penalises big mistakes (3 → 0) much more than small ones (3 → 2).

**32. Why isn't accuracy enough?**
- Short: most eyes are stage 0, so accuracy hides failures on rare stages and ignores how wrong an error is.

**33. What are your main results?**
- Short: development QWK 0.893 (IDRiD-val) and 0.918 (APTOS-val); locked IDRiD test 0.816; DeepDRiD 0.780.
- Deep: referable sensitivity 93.7% / 95.0% dev, 90.5% locked IDRiD, 93.0% DeepDRiD [Part 39].

**34. What is your AUROC and why doesn't it settle safety?**
- Short: 0.943 on the locked IDRiD test, 0.946 on DeepDRiD. AUROC measures ranking; it does not stop individual dangerous errors.

**35. How small are your test sets?**
- Short: the IDRiD clean test is 102 images (5 at grade 1), so intervals are wide — QWK 0.816 [0.731, 0.883].

**36. How good is segmentation?**
- Short: modest and lightly validated: IDRiD-val Dice MA 0.275, HE 0.422, EX 0.559, SE 0.447 on 10 images (SE 5).

---

## F. Clinical-safety questions

**37. Why did automatic routing fail?**
- Short: on the locked IDRiD test, 5 of 63 referable eyes (7.9%, upper bound 17.6%) passed every check and were routed to routine; our target was 2.5%, tolerance 4.5%.
- Deep: all five were confident stage-0 calls (confidence 0.78–0.96), one true grade 3. Confidence and the quality gate cannot catch
  errors the model is sure about [Part 30].

**38. If routing failed, why is the project useful?**
- Short: grading and ranking held up (QWK 0.82, AUROC 0.94), so it can order a specialist's worklist and catch retakes — with a clinician deciding every case.
- Do not say: "routing basically works".

**39. What if the AI is confidently wrong?**
- Short: it happens — a grade-3 eye was called stage 0 at 0.956 confidence. That is why a clinician reviews every case and we don't allow autonomous discharge.

**40. What does "99%" mean on the screen?**
- Short: a calibrated estimate fitted on held-out development data — "on similar images in the past, about this often". Not clinical certainty.

**41. What happens if one eye is missing?**
- Short: the patient is marked "incomplete screening" and can never be routed to routine.

**42. What happens with a blurry image?**
- Short: the heuristic quality check flags blur/darkness/brightness/non-fundus and asks for a retake; a second failure sends the eye to a clinician.
- Deep: it is a heuristic, not a validated gradability model — it agreed with DeepDRiD's quality labels only 53.6% of the time, and it missed heavily downscaled photos in our robustness test [Part 27].

**43. Does the clinician's correction change the result?**
- Short: it is stored and printed on the doctor report, and it protects later visits; but routing of that same visit still uses the AI stage. We list that as a gap.

**44. How do you detect PDR?**
- Short: we don't detect its defining signs. The grader may call stage 4 from the whole image (recall 4/12 IDRiD-val, 22/39 APTOS-val), and stages 3 and 4 both go to expedited review.

---

## G. Rural-deployment questions

**45. Why rural?**
- Short: that is where specialists are scarcest and recalling a patient costs the most — so catching retakes and ordering the worklist matter most.

**46. How would it run in a camp?**
- Short: one laptop with the app; the health worker uploads both eyes, sees retake reasons immediately, and the clinician reviews a sorted worklist.
- Do not say: "works fully offline anywhere" (we don't advertise that).

**47. How fast is it?**
- Short: about 1 second per image on our RTX 3050 laptop GPU and 1.4 s on CPU; about 2–3 s per two-eye patient.

**48. Hindi?**
- Short: the patient summary can be printed in Hindi; it is fixed wording that has not yet been reviewed by a native-speaking clinician.

---

## H. Explainability questions

**49. Why should a doctor trust Grad-CAM?**
- Short: they shouldn't trust it as diagnosis — it shows where the grader's evidence came from, a sanity check, not a lesion map.
- Deep: our faithfulness test (development data) showed hiding the cited lesions lowers the grade score far more than hiding random areas (p < 1e-5 on both sets) [Part 28].

**50. What is the difference between Grad-CAM, segmentation and the expert mask?**
- Short: attribution of the grader; predictions of separate lesion models; the human reference annotation.

**51. Where do the explanation sentences come from?**
- Short: templates filled only with measured findings — no language model; each number comes from the findings record.

**52. Are the lesion counts real lesions?**
- Short: they are connected regions in a model mask; object-level expert validation of the counts has not been done.

---

## I. Failure-analysis questions

**53. Why does Grade 1 perform poorly?**
- Short: we don't know for sure. IDRiD-val under-calls it (4 of 5 → stage 0); APTOS-val over-grades it (27 of 50 → stage 2).
- Deep: hypotheses — microaneurysm visibility at 384 px, single-grader labels, domain differences, class imbalance, cut-point placement — none proven [Part 21].

**54. Why are stages 2 and 3 confused?**
- Short: the boundary depends on haemorrhage counts per quadrant, beading and IRMA, which the grader sees only indirectly at 384 px.

**55. What failed in your project?**
- Short: autonomous routing on the locked test; the OOD score (AUROC 0.62); a disagreement flag; a separate referable head (misses above tolerance); the better segmenter (A3) was not completed.

---

## J. Adversarial judge questions

**56. How do you know the model didn't learn the camera?**
- Short: we don't fully. We trained on several datasets and tested on DeepDRiD (QWK 0.780); our OOD score could not even separate IDRiD from APTOS images well (AUROC 0.62). A per-camera analysis has not been done.

**57. Isn't 0.893 QWK inflated?**
- Short: it is a development number used to compare candidates; that is why we report the locked 0.816 next to it.

**58. You picked thresholds after seeing the data?**
- Short: no — cut points, calibration and routing thresholds were fitted only on the 2,813-image inner hold-out and never refitted on validation or test.

**59. Isn't this just a Kaggle model with a UI?**
- Short: the difference is the process — integrity audit, pre-registered decisions, calibrated deferral, patient-level logic, and a locked evaluation that we report even where it failed.

**60. How would this become clinically deployable?**
- Short: multi-site prospective validation, shadow deployment, task-aware gradability, advanced-sign detection, workflow and usability studies, security/privacy, and regulatory approval [Parts 37–38].
- Do not say: "it is ready for clinics".
