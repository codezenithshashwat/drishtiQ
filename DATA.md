# Data

No image data is committed. Place each dataset at the path below; raw folders are treated as read-only.

| Dataset | Source | Licence / terms | Local path | Role |
|---|---|---|---|---|
| IDRiD | IEEE DataPort, Porwal et al. (2018) | CC BY 4.0 | `data/raw/IDRiD/` | Grading train/val; segmentation train/val. Clean grading test (102 images) is **locked** |
| MMRDR (CFP subset only) | figshare, doi:10.6084/m9.figshare.29423747.v2; Tang et al., Sci Data 13:639 (2026) | CC BY 4.0 | `data/raw/MMRDR/` (archive) → extract `MMRDR-CFP/` only | Grading training (derived from OIA-DDR: training side only) |
| APTOS-2019 | Kaggle competition "APTOS 2019 Blindness Detection" | Kaggle competition rules (accept on Kaggle) | `data/raw/APTOS2019/` (`train_images/`, `train.csv`) | Grading training |
| DDR | github.com/nkicsl/DDR-dataset (official Google Drive / Baidu links) | CC BY-NC-SA 4.0 (non-commercial, share-alike) | `data/raw/DDR/` | Segmentation training (lesion masks). Training side only |
| DeepDRiD (regular fundus) | github.com/deepdrdoc/DeepDRiD (`regular_fundus_images`, sparse checkout) | CC BY-SA 4.0 | `data/raw/DeepDRiD/` | **Locked external test** (1,988 of 2,000 images after the leak check; audit in `results/audit/deepdrid/`); evaluated once after rc-1 |
| Messidor-2 | ADCIS / LaTIM; adjudicated grades: Krause et al. (2018) | ADCIS licence agreement | `data/raw/Messidor2/` | **Locked external test**: evaluated once, never used for tuning |

## Kaggle private datasets

Build the upload folders (hard links to raw data, so no extra disk space; the folders are git-ignored):
```
.venv\Scripts\python src\data\kaggle_bundles.py idrid-dev
.venv\Scripts\python src\data\kaggle_bundles.py mmrdr-cfp
```
| Upload folder | Contents | Check |
|---|---|---|
| `kaggle_upload/idrid-dev/` | 404 clean grading-train images, 50 dev segmentation images + masks, frozen split CSVs (630 files) | 0 matches against the 133 locked images (clean grading test, quarantined conflicts, segmentation test) by file SHA-256 and decoded-pixel hash |
| `kaggle_upload/mmrdr-cfp/` | `img/` (11,118 JPEGs) + `FP.csv` | Archive parts MD5-verified against figshare; member CRC-32 checked on extraction |

Each folder holds `MANIFEST.csv` (path, bytes, SHA-256) and `dataset-metadata.json`. To upload:
1. Edit `dataset-metadata.json`: replace `<your-kaggle-username>`.
2. Web: kaggle.com → Datasets → New Dataset → drag the folder → set **Private** → Create.
   Or CLI (needs your own `kaggle.json`): `kaggle datasets create -p kaggle_upload/idrid-dev --dir-mode zip` (new datasets are private by default).
3. APTOS-2019: in the notebook, use Add Data → Competitions → "APTOS 2019 Blindness Detection" (accept the rules once).

Rules:
- DDR- and EyePACS-derived data (including MMRDR-CFP) are never used as a test set.
- New training data is exact- and perceptual-hash checked against the IDRiD clean test and Messidor-2 before use.
- Frozen evaluation splits live in `configs/splits/`. The public repository keeps only `SPLITS.json` (file hashes); the per-image split CSVs carry dataset grades and are regenerated from the official downloads, see [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Image credit

Fundus image: IDRiD, CC BY 4.0. The landing page shows the app's case view captured with one IDRiD validation photograph (Porwal et al., 2018, IEEE DataPort). It is the only fundus image in this repository.
