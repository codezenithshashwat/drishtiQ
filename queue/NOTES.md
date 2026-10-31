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

- 2026-10-30 16:50 — **Queue stopped by the user's instruction; GPU vacated for Approach V2 Step 4.**
  The A3 retry (attempt 2, started 15:18:30) again ran at ~18 W / 100% util with no step-500 line for 92 min: the stalled state
  survived the process restart. No reboot happened (Windows last boot 2026-10-27 03:36; the user's restart did not take place).
  Stopped: queue runner (PIDs 21824/13692), A3 fold 2 (34632/12268), app backend on :8000 (17892/43080). keep_awake left running.
  nvlddmkm event 153 at 16:50:51 coincides with stopping the stalled context (same as 15:18:29).
  Health check afterwards, no reboot: idle P8 2 W; 60 s fp16 matmul load P0 ~60 W (cap 59 W), 2460-2505 MHz, 70 °C, 17.2 TFLOPS.
  So the GPU itself is fine; the stall belonged to the A3 process's CUDA context created before the lid standby / FECS errors.
  Incident chain: lid standby 13:20-13:29 → 510 FECS exceptions 14:00-14:13 → low-power stall of A3 fold 2 (both attempts) → stopped.
  A3 (fold 2 onward; folds 0-1 done, 10 out-of-fold maps cached) is deferred by the user. The runner is NOT relaunched; jobs.yaml unchanged.
  Rule from now on: while the queue trains, nothing else uses the GPU; automated tests/scripts run with RS_DEVICE=cpu, verified
  with nvidia-smi (amended 21:50: CUDA_VISIBLE_DEVICES=-1 itself crashes processes with this NVIDIA driver, see ADR-044).
