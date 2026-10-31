# IDRiD suitability matrix

Task-relative internal research ratings. Resolve exact duplicate/label conflict before model decisions.

| Task | IDRiD suitability | Evidence | Main limitation | Recommended role |
| --- | --- | --- | --- | --- |
| DR grading | Limited until integrity issue resolved | 516 labeled images, ordinal grades 0–4 | Exact train/test duplicate has conflicting grades, plus small imbalanced single source | Internal benchmark; test fine-tuning hypotheses |
| Lesion segmentation | Strong | 81 expert-annotated photographs | Small selected diseased subset; incomplete type coverage | Pixel annotation research |
| MA segmentation | Moderate | 81 masks | Tiny components vulnerable to resizing | Small-lesion internal benchmark |
| HE segmentation | Moderate | 80 masks | Absent-mask semantics; limited diversity | Internal lesion research |
| EX segmentation | Strong | 81 masks | One acquisition domain | Internal pixel annotation benchmark |
| SE segmentation | Limited | 40 masks | Few examples and partial coverage | Exploratory segmentation |
| Anatomical localization | Strong | 1032 center records plus OD masks | Coordinate convention and domain limits | OD/fovea spatial research |
| Image-quality modeling | Unsuitable / unsupported | Descriptive proxies only | No clinical gradability labels | Outlier review only |
| Internal training | Moderate | Organizer train partition | Small effective sample; unknown patients | Preserve test; define validation within train |
| Internal validation | Limited | Training can be subdivided | No official validation; patient grouping unavailable | Prespecify training-only validation |
| Internal testing / evaluation | Moderate | Organizer test and labels | Small strata; test reuse bias | Locked internal test, per-class uncertainty |
| External validation after IDRiD training | Unsuitable / unsupported | Same underlying collection | Internal test after IDRiD training | Obtain independent licensed dataset |
| External validation of an independently trained model | Moderate | Distinct source only if training excludes IDRiD and related images | Narrow acquisition domain; overlap must be ruled out | Possible external benchmark, not broad deployment proof |
| Domain-generalization evaluation | Unsuitable / unsupported | Single documented clinic/camera | No independent domain contrast | Evaluate separate institutions/cameras |
| Multi-task learning | Moderate | 3 content-matched grading/segmentation groups | Partial supervision; cross-task split leakage | Content-group protected exploration |
| Explainability research | Moderate | Lesion and anatomy reference annotations | Localization overlap does not prove faithfulness | Reference localization and human study later |
