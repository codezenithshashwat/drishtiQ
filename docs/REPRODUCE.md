# Reproducing the label-derived files

The public repository does not republish per-image dataset labels: the split CSVs, audit manifests and fingerprints that carry grades, lesion-mask statistics, landmark coordinates and prediction tables with true grades are left out (see the last block of `.gitignore`). Aggregate results stay in the repository: `results/registry.csv`, `results/KEY_NUMBERS.md`, the scorecards, `results/coverage/curve.png` and `docs/research/ARCHITECTURE_DECISION_LOG.md`.

Everything left out is regenerated from the official dataset downloads with the scripts below. Get the datasets first and place them as described in [DATA.md](../DATA.md); raw folders are only read. Run every command from the repository root with the project environment (`.venv\Scripts\python`), with `src` on `PYTHONPATH` for the `-m eval` step.

`configs/splits/SPLITS.json` records the SHA-256 of every frozen split file, so a regenerated split can be checked byte for byte against the one used for the reported results.

## Order

| Step | Command | Regenerates |
|---|---|---|
| 1. IDRiD audit | `src\data\audit_idrid.py` | `outputs/metrics/idrid_*` (labels, localisation coordinates, mask component areas, resolution analysis, cross-task mapping) |
| 2. IDRiD integrity | `src\data\resolve_idrid_integrity.py` | duplicate resolution tables, segmentation annotation policy, clean manifests in `data/interim/manifests/` |
| 3. APTOS audit | `src\data\audit_aptos.py fingerprint`, then `audit`, then `split` | `results/audit/aptos/*` and `configs/splits/aptos_train.csv`, `aptos_val.csv` |
| 4. MMRDR-CFP | `src\data\extract_mmrdr.py extract`, `src\data\audit_mmrdr.py fingerprint`, `audit_mmrdr.py audit`, `src\data\mmrdr_manifest.py` | `results/audit/mmrdr/*.csv`, `configs/splits/mmrdr_train.csv` |
| 5. DDR segmentation | `src\data\extract_ddr.py extract`, `src\data\audit_ddr.py`, `src\data\ddr_splits.py` | `results/audit/ddr/ddr_seg_fingerprints.csv`, `configs/splits/ddr_seg_*.csv` |
| 6. IDRiD splits | `python -m eval make-splits` | `configs/splits/idrid_grading_devtrain.csv`, `idrid_grading_val.csv`, `idrid_seg_train.csv`, `idrid_seg_val.csv` (refuses to overwrite existing files) |
| 7. DeepDRiD lock | `tools\audit_deepdrid.py` | `results/audit/deepdrid/*`, the locked set in `data/interim/manifests/` |
| 8. Model-selection study | `src\model_selection\run_study.py` | `outputs/metrics/model_selection/grading_folds.csv`, per-run `validation_predictions.csv`, `native_validation_metrics*.csv`, `selected_grading_OOF_predictions.csv`. This retrains the study models (GPU, hours) |
| 9. Segmentation evaluation | `python -m eval segment` | per-image Dice (`results/runs/*/per_image_dice.csv` and the `per_image` block of the run's `metrics.json`) |

Steps 1 to 7 only read images and labels and take minutes. Steps 8 and 9 need the model checkpoints (see [MODELS.md](../MODELS.md)) or retraining.

## Checks

- After step 6, compare the split files with `configs/splits/SPLITS.json`; a mismatch means a different dataset version or download.
- `tools\reproduce.py --check` recomputes the registry metrics from the run files once the splits and checkpoints are in place.
- Tests that need the removed files skip with a reason naming the missing file; with the files regenerated they run again.
