# GPU queue status

Updated 2026-10-30T15:18:30. Queue process PID 13692. Running: a3_train. Next: a3_train.
Last GPU reading 15:16: 55 °C, 100% util, 3709 MiB VRAM; 350 GB disk free.

Timeline estimates assume jobs run in the order below; disabled jobs are counted where they sit.

| Job | What | Est. GPU min | Status | When | Result |
|---|---|---|---|---|---|
| a2_swap | A2: ADR-013 rule on fixed candidate reg384 s17 (venv runs 081750 / 082105) vs comparator; switch app grader if it passes | 1 | done | 08:33 to 08:40 | ADR-013 PASS; idrid dQWK +0.098 [+0.036, +0.171], aptos dQWK +0.198 [+0.152, +0.247]; app grader switched |
| a3_baseline_ddr | A3 prerequisite: v0.1 (v0 + pp_v2) evaluated on DDR-test (225) for the ADR-016 comparison | 10 | done | 08:40 to 08:52 |  |
| b5b6_metrics | B5 calibration/abstention (ADR-019) + B6 triage metric (ADR-020) for the current app grader | 15 | done | 19:52 to 19:53 | B5/B6 for convnext_tiny_mixed_reg_plain384_datasetbal_sqrtcw_v1_s17.pt: tau 0.55; idrid: ECE P(ref) 0.040->0.083, coverage 0.91 acc retained 0.717 vs all 0.673, AUROC 0.992, workload@95% 0.59; aptos: ECE P(ref) 0.077->0.027, coverage 0.94 acc retained 0.831 vs all 0.811, AUROC 0.975, workload@95% 0.44 |
| a2_seed23 | A2 seeds: reg384 seed 23 (same recipe) | 80 | done | 08:52 to 19:52 |  |
| a3_train | A3: U-Net/R18 on DDR train+valid + IDRiD dev (5-fold CV, fold 4 = candidate); pp re-selection on CV; IDRiD-val + DDR-test; ADR-016 per lesion | 400 | running | started 19:53, est. end 02:33 | A3 fold 1 trained; 10 out-of-fold maps in results\cache\seg_a3_cv |
| dme_refit | DME rule refit on dev-train with the app segmenter (after A3); report IDRiD-val; app uses the refit | 25 | pending | est. end Fri 15:43 |  |
| s1_thresholds | S1 (ADR-027): thresholds for macro-F1 on the inner hold-out; rule vs app system | 15 | pending | est. end Fri 15:58 |  |
| seg_ensemble_tta | Segmentation (ADR-031 #1): A3 5-fold ensemble + flip TTA; pp re-selection; per-lesion rule vs app segmenter; FROC | 60 | pending | est. end Fri 16:58 |  |
| seg_ma_variant | Segmentation (ADR-031 #2): MA variant (green local-contrast input, Tversky), 5 folds; rule for MA vs app segmenter | 380 | pending | est. end Fri 23:18 |  |
| a2_seed41 | A2 seeds: reg384 seed 41 (same recipe) | 80 | pending | est. end Sat 00:38 |  |
| a2_ensemble | A2 ensemble: 3-seed reg384 vs single s17, ADR-017; switch app grader only if s17 is the app grader and the rule passes | 10 | pending | est. end Sat 00:48 |  |
| s2_stage01 | S2 (ADR-028): stage 0 vs 1 specialist at 768 px; rule g1 vs app system | 240 | pending | est. end Sat 04:48 |  |
| s3_stage34 | S3 (ADR-028): stage 3 vs 4 specialist at 512 px, class 4 oversampled; rule g4 vs app system | 60 | pending | est. end Sat 05:48 |  |
| s4_corn | S4 (ADR-029): CORN ordinal grader, warm start from reg384 s17; ADR-013 rule vs app system | 80 | pending | est. end Sat 07:08 |  |
| eyepacs | Conditional EyePACS 2015 (ADR-037): trigger on APTOS-val stage-1/4 recall; download, audit, retrain, ADR-013 | 60 | pending | est. end Sat 08:08 |  |
| seg_upgrade_loss | Conditional segmentation loss upgrade per lesion (ADR-036): focal + Dice where CV AUPR is > 0.05 short of target | 380 | pending | est. end Sat 14:28 |  |
| seg_upgrade_encoder | Conditional segmentation encoder upgrade per lesion (ADR-036): ConvNeXt-T U-Net where still > 0.05 short | 450 | pending | est. end Sat 21:58 |  |
| dme_refit_final | DME rule refit on dev-train with the final segmenter (ADR-014); report IDRiD-val | 25 | pending | est. end Sat 22:23 |  |
| a4_fusion | A4 lesion-to-grade fusion (ADR-021): fit on inner hold-out, evaluate, swap rule + stage-1 recall gain on APTOS-val | 180 | pending | est. end Sun 01:23 |  |
| pseudo_label | Pseudo-labelling on APTOS test_images (ADR-018): leak check, d fixed on inner hold-out, student reg384 s17, ADR-013 comparison vs single s17. ADR-018a: swap rule applied vs the app grader | 100 | pending | est. end Sun 03:03 |  |
| deepdrid_relock | Re-audit DeepDRiD lock after pseudo-labelling (adds the APTOS test images to the leak check; ADR-034a) | 5 | pending | est. end Sun 03:08 |  |
| faithfulness | Explanation faithfulness test (ADR-032): hide cited lesions vs equal-area control | 70 | pending | est. end Sun 04:18 |  |
| r2_bad_input | R2 bad-input safety (ADR-023): non-fundus, blurred, dark inputs never get a confident stage | 5 | pending | est. end Sun 04:23 |  |
| r1_robustness | R1 robustness (ADR-022): 10 degradations on IDRiD-val + APTOS-val, inference only | 60 | pending | est. end Sun 05:23 |  |
| r3_gradcam_audit | R3 Grad-CAM shortcut audit (ADR-024) on IDRiD-val + APTOS-val | 20 | pending | est. end Sun 05:43 |  |
| r4_quality_gate | R4 quality gate on DDR-train ungradable vs gradable (ADR-025), CPU only | 30 | pending | est. end Sun 06:13 |  |
| b5b6_final | B5 calibration/abstention (ADR-019) + B6 triage metric (ADR-020) for the current app graderafter ensemble/pseudo-label decisions; no-op if the grader did not change | 15 | pending | est. end Sun 06:28 |  |
| tta_final | TTA (ADR-030): flip + rotations on the final system; ADR-013 rule; calibration refit | 90 | pending | est. end Sun 07:58 |  |
| benchmark_final | Final timing on the final system (GPU / CPU), then refresh all generated numbers | 15 | pending | est. end Sun 08:13 |  |
| rc1_check | rc-1 readiness check (ADR-038): queue finished, preflight, reproduce, tests; never tags | 15 | pending | est. end Sun 08:28 |  |

Logs: queue/logs/ (queue.log, <job>.step<N>.log, gpu.csv). Decisions: queue/decisions/. Stop: create queue/STOP.

## Operator notes

- 2026-10-30 15:18 — **A3 fold 2 treated as hung and its training process stopped (rule set by the user: no step progress for > 90 min).**
  Fold 2 started 13:47:44; by 15:18 it had logged no 500-step line and written no resume file (fold 0 logged step 500 after 544 s).
  The process was alive (CPU ~1.4 cores, 7 GB working set) and the GPU showed 100% utilisation but only ~19-21 W at P0 / 2505 MHz
  (normal training 40-50 W) with no throttle reasons. The NVIDIA driver logged nvlddmkm event 13 "Graphics FECS Exception"
  510 times between 14:00 and 14:13, after a lid standby 13:20-13:29 (Kernel-Power 506/507).
  Likely cause: the GPU context stalled after the standby/FECS exceptions (not confirmed; py-spy not installed, no stack captured).
  Decision: stopped only the training python (PID 19076; its launcher 45228 exited with it). Queue runner PID 13692 left running;
  it retried a3_train from step 2 (fold 2) at 15:18:30 (attempt 2 of 2; no resume file existed, so fold 2 restarts at step 0).
  No power settings changed.
