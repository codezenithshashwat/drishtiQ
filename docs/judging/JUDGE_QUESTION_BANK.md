# Judge Question Bank

Answer status: ✅ answerable from evidence now · 🟡 partial / needs a stage · ❌ cannot answer yet.
Every answer must cite a Claims Ledger ID (`docs/research/CLAIMS_LEDGER.md`).

## Clinical
| Question | Status | Answer basis |
|---|---|---|
| Why screening rather than diagnosis? | ✅ | No prospective validation, no regulatory clearance; output is a referral suggestion for a clinician |
| Who makes the final decision? | ✅ | Clinician; UI supports override |
| What does each DR grade mean? | ✅ | ICDR (Wilkinson 2003): none / mild (MA only) / moderate / severe (4-2-1 rule) / PDR (NV or vitreous/preretinal haemorrhage) |
| Why are MA/HE/EX important? | ✅ | MA is the earliest sign (defines mild); HE/EX are moderate+ markers; EX near the macula indicates DME risk |
| Can these lesions alone determine PDR? | ✅ | No. PDR needs NV/VH; severe NPDR needs 4-2-1 (HE in 4 quadrants, VB in 2, IRMA in 1). This is why we test MMRDR's VB/IRMA/NV labels (H04) |
| What happens with an ungradable image? | 🟡 S7 | Quality gate → "retake / review"; proxy only, not validated gradability |
| What happens when the model is uncertain? | 🟡 S8 | Calibrated abstention → "insufficient confidence — clinician review" |
| Why isn't OCT required? | ✅ | Problem statement is fundus-based; OCT is for DME thickness, out of scope |
| What is DME and how is it different? | ✅ | Macular thickening/exudation; graded separately from DR severity; OCT is the reference |

## Dataset
| Question | Status | Answer basis |
|---|---|---|
| Why IDRiD? | ✅ | Only common public set with both grades and pixel masks for MA/HE/EX/SE at high resolution; Indian population |
| Why MMRDR? | 🟡 S1 | 11k CFP, 1,302 mild NPDR, image-level lesion labels incl. VB/IRMA/NV (C13–C15) |
| Why not EyePACS / APTOS / DDR? | ✅ | EyePACS is in RETFound pretraining; DDR is MMRDR's parent; APTOS used as secondary external |
| How many images? Class distribution? | 🟡 | IDRiD ✅ (C03); MMRDR per-grade ✅ from paper, per-split after S1 |
| Who annotated? Standard? | ✅ | IDRiD: per IDRiD paper; MMRDR: 4 ophthalmologists + 1 retina specialist, κ ≥ 0.75 (C13) |
| What duplicates/leakage did you find? | ✅ | C01–C02 |
| Why exclude ten IDRiD files? | ✅ | C03 |
| Did you alter labels? | ✅ | No |
| Do you know patient identities / guarantee independence? | ✅ | No, for both IDRiD and MMRDR-CFP (C14) |
| Does MMRDR overlap DDR/OIA-DDR? | ✅ | Yes, it is derived from it (C14) |
| Why is your external dataset truly external? | 🟡 S1 | Messidor-2: France, different cameras, not in RETFound pretraining, not DDR; hash-checked |

## Model
| Question | Status | Answer basis |
|---|---|---|
| Why RETFound / not ResNet, EfficientNet, ConvNeXt, ViT? | 🟡 S3 | We compared ResNet50/EffNet-B0/ConvNeXt-T/Swin-T (C05); RETFound result pending |
| Why not train from scratch? | ✅ | 404 images |
| What is SSL / MAE? | ✅ | Mask 75% of patches, reconstruct; learns retinal structure without labels (C11) |
| What evidence shows RETFound helps YOUR data? | ❌ until S3 | — |
| Why does Grade 1 fail? | 🟡 | n=18 (C06); hypothesis: MA visibility at 224 (H02) |
| Why QWK, not accuracy? | ✅ | Ordinal; distance-weighted penalties; accuracy hides 4→0 errors |

## Resolution
| Question | Status | Answer basis |
|---|---|---|
| Why 224? Didn't your audit show MA loss at 224? | ✅ | Yes (C04). Grading at 224 is a baseline; lesion evidence comes from a high-res segmentation path |
| Why did native patches perform worse? | 🟡 S6 | Observed (C10); hypothesis H03 under test |
| How are you preserving tiny lesions? | 🟡 S6 | — |

## Segmentation
| Question | Status | Answer basis |
|---|---|---|
| Why SegFormer / U-Net? | 🟡 S6 | Short screen only (C09) |
| What happens when a mask is unavailable? Does missing mean no lesion? | ✅ | Loss is masked for that channel; missing ≠ negative |

## Explainability
| Question | Status | Answer basis |
|---|---|---|
| Is Grad-CAM a segmentation map? | ✅ | No; it shows regions that influenced the classifier |
| How do you know the model isn't using shortcuts? | 🟡 S9 | Sanity checks + overlap with expert masks |

## Generalisation / Safety
| Question | Status | Answer basis |
|---|---|---|
| Another camera / hospital / country? | ❌ until S14 | Messidor-2 single locked run |
| Can the model miss PDR? Dangerous under-grading rate? | 🟡 | CV rate exists (scorecard); test rate after S14 |
| Can a doctor override? | 🟡 S12 | Yes, by design |

## Engineering
| Question | Status | Answer basis |
|---|---|---|
| Latency? GPU needed? CPU? Model size? Internet? | ❌ until S15 | — |
| How is patient data handled/stored? | 🟡 S11 | In-memory by default, offline |

## Research honesty
| Question | Status | Answer basis |
|---|---|---|
| What did NOT work? | ✅ | C06, C08, C09, C10 |
| Biggest limitation? | ✅ | No patient-level independence; no prospective/clinical validation; tiny mild-NPDR set |
| Six more months? | ✅ | Patient-level multi-site data, handheld cameras, prospective reader study, gradability labels |
