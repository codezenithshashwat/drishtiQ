# Data card: RetinaScreen

Which datasets are used, how, and under what terms. Paths and audit details: [DATA.md](../DATA.md). No image or label file is in the repository.

| Dataset | Images used | Labels | Role | Licence |
|---|---|---|---|---|
| IDRiD (Porwal et al., 2018) | Grading: dev-train 303, validation 101, clean test 102 (locked). Segmentation: 50 dev images (5-fold CV) | ICDR stage; DME risk; pixel masks for MA, HE, EX, SE | Training, validation, locked test | CC BY 4.0 |
| APTOS 2019 (Kaggle) | Train split 2,929; validation split 518 | ICDR stage (one grader) | Training, validation; test images only for record-only pseudo-labelling (leak-checked) | Kaggle competition rules |
| MMRDR colour fundus subset (Tang et al., 2026) | 10,831 (training side only) | ICDR stage | Grading training | CC BY 4.0 |
| DDR (Li et al., 2019) | Lesion segmentation train + valid 527 (training), test 225 (segmentation validation only); grading-train ungradable images for the quality-gate check | Pixel masks; grades incl. "ungradable" | Segmentation training; validation of the quality gate | CC BY-NC-SA 4.0 |
| DeepDRiD (regular fundus) | Locked, evaluated once after `rc-1` | ICDR stage; image quality | External test | As recorded in the audit |
| Messidor-2 | Locked, evaluated once after `rc-1` | Adjudicated grades (Krause et al., 2018) | External test | ADCIS licence agreement |

## How the data were checked

- **Duplicates and leaks:** a calibrated structure hash (distance ≤32 = duplicate, ≤42 = leak match) was run across all sets. Near-copies were removed from training, and the locked sets were checked against everything used for training or selection.
- **Overlaps:** DDR and MMRDR share many images (MMRDR derives from the same source). That's acceptable on the training side. DDR-test images are excluded from any analysis where the grader would have seen them (ADR-014, ADR-021).
- **Validation sets** are never used for training, threshold fitting or selection. Every model change is decided by a rule written down before its result.

## Known biases and limits

- **Population:** all grading sets except MMRDR come from India; MMRDR adds Chinese data. Camera types are limited to those in these datasets.
- **Labels:** APTOS has one grader per image and known label noise near stage boundaries. IDRiD labels come from experts.
- **Under-represented classes:** stage 1 and stage 4 have the fewest examples, which matches where the grader is weakest.
- **Masks:** IDRiD masks are not available for every lesion type in every image; missing masks are treated as unknown, not as "no lesion".

## Acknowledgements

Thank you to the IDRiD, APTOS / Aravind Eye Hospital, MMRDR, DDR, DeepDRiD and Messidor teams for collecting, grading and sharing these images.
