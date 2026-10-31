# IDRiD research-grade dataset audit

## Scope, evidence categories and execution

Audit date: 2026-10-28 (Asia/Calcutta); fixed seed 20261028. No training or final model/preprocessing/resolution/loss/referral decision. **Patient-level leakage cannot be fully audited from the publicly available identifiers.**

**Verified local observations** are computed in the CSV tables. **Documentation facts** are attributed to sources below. **Interpretations** explain consequences, not clinical diagnoses. **Unknowns** remain explicit. **Future implications** are hypotheses and evaluation requirements, not selected methods.

## Critical verified finding: split overlap with inconsistent labels

| content_sha256 | split | image_id | DR_grade | DME_label | path |
| --- | --- | --- | --- | --- | --- |
| 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | train | IDRiD_118 | 0 | 0 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_118.jpg |
| 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | test | IDRiD_064 | 3 | 0 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\b. Testing Set\IDRiD_064.jpg |
| 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | train | IDRiD_028 | 4 | 2 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_028.jpg |
| 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | train | IDRiD_327 | 3 | 2 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_327.jpg |
| 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | train | IDRiD_045 | 2 | 0 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_045.jpg |
| 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | train | IDRiD_333 | 2 | 1 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_333.jpg |
| e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | train | IDRiD_021 | 1 | 0 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_021.jpg |
| e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | train | IDRiD_391 | 2 | 0 | data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\1. Original Images\a. Training Set\IDRiD_391.jpg |

The bytes and decoded pixels establish identical image content, yet these CSV grades disagree. This is a local dataset integrity failure, not an inferred clinical diagnosis. Archive/extraction comparisons indicate whether the retained packages also contain the issue. The organizer documentation claim of no duplicates conflicts with this observed local result. Do not alter raw files or silently repair labels. Resolve author/source provenance and prespecify any exclusion/label policy before training. Review exact_duplicate_label_conflict.png. The cross-task mapping retains all conflicting label records and leaves its single-valued DR/DME fields unset for ambiguous groups.

## Qualified cross-task image correspondence

| match_status | candidate_cross_split | segmentation_images |
| --- | --- | --- |
| high_similarity_candidate | False | 34 |
| high_similarity_candidate | True | 13 |
| unresolved_candidate | False | 14 |
| unresolved_candidate | True | 17 |
| verified_exact | False | 3 |

Exact decoded matching alone cannot recognize recompression. Every segmentation image was compared to every grading image using 64×64 bilinear RGB mean absolute error, Pearson correlation and second-best separation. High-similarity candidates require MAE≤2/255, correlation≥0.995 and a ≥5 intensity-unit margin to the second best. Full-resolution MAE/max/equal-pixel fractions are measured for nonexact high-similarity pairs. These criteria are heuristic evidence of shared imagery, not proof of patient or byte identity. Candidate grading labels remain explicitly qualified in separate candidate fields. Review idrid_cross_task_similarity_candidates.csv and cross_task_candidate_pairs.png; exact and approximate results are never silently conflated.

## CSV export artifacts distinguished from annotations

| path | raw_csv_rows | blank_padding_rows | annotation_rows |
| --- | --- | --- | --- |
| data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\2. Groundtruths\a. IDRiD_Disease Grading_Training Labels.csv | 413 | 0 | 413 |
| data\raw\IDRiD\original\B. Disease Grading\B. Disease Grading\2. Groundtruths\b. IDRiD_Disease Grading_Testing Labels.csv | 103 | 0 | 103 |
| data\raw\IDRiD\original\C. Localization\C. Localization\2. Groundtruths\1. Optic Disc Center Location\a. IDRiD_OD_Center_Training Set_Markups.csv | 515 | 102 | 413 |
| data\raw\IDRiD\original\C. Localization\C. Localization\2. Groundtruths\1. Optic Disc Center Location\b. IDRiD_OD_Center_Testing Set_Markups.csv | 515 | 412 | 103 |
| data\raw\IDRiD\original\C. Localization\C. Localization\2. Groundtruths\2. Fovea Center Location\IDRiD_Fovea_Center_Testing Set_Markups.csv | 515 | 412 | 103 |
| data\raw\IDRiD\original\C. Localization\C. Localization\2. Groundtruths\2. Fovea Center Location\IDRiD_Fovea_Center_Training Set_Markups.csv | 515 | 102 | 413 |

All-blank core rows are export padding, not missing patient annotations. Exact raw schema/missing/duplicate counts remain in idrid_csv_schema.csv; the localization metadata contains usable nonblank rows. One training grading extra-field cell at IDRiD_405 contains only whitespace; it is semantically empty and not an extra target. No raw CSV was rewritten. Initial localization bounds/duplicate failures caused by parsing padding as annotations were corrected by explicitly classifying those rows; this was a parser issue, not a dataset coordinate failure.

## MA collapse and merger tracing

| target_width | original_components | disappeared | collapsed_to_one_target_pixel | target_regions_merging_multiple_source_components | source_components_in_merged_regions | source_components_fragmented |
| --- | --- | --- | --- | --- | --- | --- |
| 224 | 3497 | 1240 | 1814 | 77 | 164 | 0 |
| 384 | 3497 | 197 | 1174 | 67 | 141 | 0 |
| 512 | 3497 | 47 | 477 | 56 | 115 | 0 |
| 1024 | 3497 | 2 | 12 | 19 | 39 | 0 |
| 2048 | 3497 | 0 | 0 | 7 | 14 | 0 |

Collapsed-to-one-pixel counts are surviving source components represented by exactly one target pixel. Merged-region counts explicitly trace multiple source IDs into each eight-connected target region; fragmentation is counted separately. These supplement the net merger proxy in the all-lesion resolution table.

## Repeated-image center annotation variation

| content_sha256 | anatomy | annotation_rows | x_range_pixels | y_range_pixels | split_ids |
| --- | --- | --- | --- | --- | --- |
| 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | OD | 2 | 4.0 | 7.0 | train:IDRiD_118;test:IDRiD_064 |
| 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | fovea | 2 | 15.0 | 0.0 | test:IDRiD_064;train:IDRiD_118 |
| 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | OD | 2 | 7.0 | 0.0 | train:IDRiD_028;train:IDRiD_327 |
| 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | fovea | 2 | 0.0 | 34.0 | train:IDRiD_028;train:IDRiD_327 |
| 56edb589ae93c14547a7d858a5b4d7d8796e0ed8d16a2343469b68cd2ce340f9 | OD | 2 | 11.0 | 15.0 | train:IDRiD_073;train:IDRiD_375 |
| 56edb589ae93c14547a7d858a5b4d7d8796e0ed8d16a2343469b68cd2ce340f9 | fovea | 2 | 12.0 | 7.0 | train:IDRiD_073;train:IDRiD_375 |
| 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | OD | 2 | 4.0 | 4.0 | train:IDRiD_045;train:IDRiD_333 |
| 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | fovea | 2 | 7.0 | 7.0 | train:IDRiD_045;train:IDRiD_333 |
| 964bd06f485fe4ae0a7f917f3af7fd00e2e33896695119e6d17b56620e9fd743 | OD | 2 | 8.0 | 11.0 | train:IDRiD_079;train:IDRiD_279 |
| 964bd06f485fe4ae0a7f917f3af7fd00e2e33896695119e6d17b56620e9fd743 | fovea | 2 | 7.0 | 0.0 | train:IDRiD_079;train:IDRiD_279 |
| e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | OD | 2 | 3.0 | 4.0 | train:IDRiD_021;train:IDRiD_391 |
| e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | fovea | 2 | 8.0 | 8.0 | train:IDRiD_021;train:IDRiD_391 |

The same decoded photographs can have slightly different center annotations across duplicate IDs. These are measured pixel disagreements, not proof of a wrong clinical location. They demonstrate reference variability even for identical imagery; pixel offsets are not physical distances.

## Mask encoding and alpha-channel handling

| mode | channels | foreground_rule | masks |
| --- | --- | --- | --- |
| P | 1 | nonzero palette index | 362 |
| RGBA | 4 | any RGB color channel >0; alpha excluded | 1 |

362 masks use indexed palettes with scalar values 0/1. IDRiD_81_EX.tif is RGBA: red is 0/255, green/blue are zero, and alpha is 255 everywhere. The actual foreground is 312,918 pixels (2.5623% of the canvas), not the opaque alpha channel. Foreground decoding excludes alpha. A final sanity check caught and corrected an initial any-channel interpretation that would have falsely labeled the entire canvas foreground. Component areas, coverage statistics, resolution tables and EX figures were regenerated from RGB foreground. Exact palette/alpha evidence is in idrid_mask_encoding_audit.csv; raw bytes were unchanged.

## 1. Inventory and extraction integrity

Actual raw root: data/raw/IDRiD, with archives and nested original/A/B/C packages. Archives are not additional samples. idrid_directory_tree.txt records every directory; inventory records every path, extension, byte count and SHA-256. Filename collisions are enumerated separately.

| component | kind | extension | count |
| --- | --- | --- | --- |
| Disease Grading | archive | .zip | 1 |
| Disease Grading | documentation | .txt | 2 |
| Disease Grading | fundus | .jpg | 516 |
| Disease Grading | table | .csv | 2 |
| Localization | archive | .zip | 1 |
| Localization | documentation | .txt | 2 |
| Localization | fundus | .jpg | 516 |
| Localization | table | .csv | 4 |
| Segmentation | archive | .zip | 1 |
| Segmentation | documentation | .txt | 2 |
| Segmentation | fundus | .jpg | 81 |
| Segmentation | mask | .tif | 363 |

Zip CRC was checked. Local archive consistency cannot establish publisher authenticity without external checksums. No remote per-file manifest was supplied; documented totals and bidirectional correspondence provide completeness evidence. Unexpected, zero-byte and unreadable outcomes appear in integrity checks.

## 2. Fundus image integrity

| component | split | images |
| --- | --- | --- |
| Disease Grading | test | 103 |
| Disease Grading | train | 413 |
| Localization | test | 103 |
| Localization | train | 413 |
| Segmentation | test | 27 |
| Segmentation | train | 54 |

| width | height | mode | channels | format | files |
| --- | --- | --- | --- | --- | --- |
| 4288 | 2848 | RGB | 3 | JPEG | 1113 |

1113 file instances correspond to 588 unique decoded-content groups. Every image was fully decoded. Metadata includes aspect ratio, mode/channels, dtype, format, file size, pixel range/mean/std, RGB moments, byte hashes and mode/size-aware decoded hashes. These tables expose grayscale, unusual dimensions and corrupt files. Cross-task duplicates are separated from cross-split leakage.

## 3–5. Disease labels, distributions and ordinal implications

idrid_csv_schema.csv preserves exact headers including whitespace, inferred types, missing counts, duplicate rows/IDs and blank trailing export columns. The first three content columns are parsed without rewriting raw CSVs. Orphan image/label matches are checked in both directions separately by split.

| split | DR_grade | count | percent |
| --- | --- | --- | --- |
| train | 0 | 134 | 32.445520581113804 |
| train | 1 | 20 | 4.842615012106537 |
| train | 2 | 136 | 32.92978208232446 |
| train | 3 | 74 | 17.91767554479419 |
| train | 4 | 49 | 11.864406779661017 |
| test | 0 | 34 | 33.00970873786408 |
| test | 1 | 5 | 4.854368932038835 |
| test | 2 | 32 | 31.06796116504854 |
| test | 3 | 19 | 18.446601941747574 |
| test | 4 | 13 | 12.62135922330097 |
| all | 0 | 168 | 32.55813953488372 |
| all | 1 | 25 | 4.844961240310078 |
| all | 2 | 168 | 32.55813953488372 |
| all | 3 | 93 | 18.023255813953487 |
| all | 4 | 62 | 12.015503875968992 |

| split | n | majority_grades | minority_grades | max_min_ratio | majority_baseline_accuracy | entropy_bits |
| --- | --- | --- | --- | --- | --- | --- |
| all | 516 | [0, 2] | [1] | 6.72 | 0.32558 | 2.07864 |
| test | 103 | [0] | [1] | 6.8 | 0.3301 | 2.09039 |
| train | 413 | [2] | [1] | 6.8 | 0.3293 | 2.07545 |

**Interpretation:** rare classes constrain learning and precision. Majority-baseline accuracy is label arithmetic, not model performance; aggregate accuracy can hide minority failure. Selected disease distributions are not population prevalence.

**Ordinal target:** observed values are checked against 0→1→2→3→4, increasing severity. Standard ICDR terms are no apparent DR, mild NPDR, moderate NPDR, severe NPDR and proliferative DR; the descriptor loosely calls grade 4 severe, so future implementation should adopt the actual grading standard explicitly. A 4→3 error is one step; 4→0 is four steps and grossly understates severity. Step distance is not calibrated clinical utility.

**Future implications:** evaluate confusion matrix, per-class sensitivity/recall, macro F1, balanced accuracy and quadratic weighted kappa with uncertainty. Kappa depends on marginals and ordinal distance. Define any referral threshold from an adopted standard later; none invented here. Sampling, weighting and ordinal formulations are possible hypotheses, not chosen approaches.

## 6. DME labels audited separately

| split | DME_label | count |
| --- | --- | --- |
| test | 0 | 45 |
| test | 1 | 10 |
| test | 2 | 48 |
| train | 0 | 177 |
| train | 1 | 41 |
| train | 2 | 195 |

| split | DR_grade | 0 | 1 | 2 |
| --- | --- | --- | --- | --- |
| test | 0 | 34 | 0 | 0 |
| test | 1 | 5 | 0 | 0 |
| test | 2 | 0 | 3 | 29 |
| test | 3 | 3 | 3 | 13 |
| test | 4 | 3 | 4 | 6 |
| train | 0 | 134 | 0 | 0 |
| train | 1 | 20 | 0 | 0 |
| train | 2 | 16 | 33 | 87 |
| train | 3 | 3 | 4 | 67 |
| train | 4 | 4 | 4 | 41 |

**Documentation:** labels represent hard-exudate occurrence/proximity to the macular center using Messidor-derived risk definitions. They are not OCT-confirmed thickening. Cross-tabs describe association, not causality or interchangeability with DR. Missing/invalid DME values are checked independently.

## 7–8. Segmentation, coverage and sparsity

| split | mask_type | images | masks | images_with_mask | images_without_mask | empty_masks | min_positive_pixels | median_positive_pixels | mean_positive_pixels | max_positive_pixels | median_image_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | MA | 54 | 54 | 54 | 0 | 0 | 804 | 9651.5 | 13054.87037 | 38066 | 0.07903 |
| train | HE | 54 | 53 | 53 | 1 | 0 | 2149 | 58339.0 | 122650.66038 | 1821322 | 0.47771 |
| train | EX | 54 | 54 | 54 | 0 | 0 | 2343 | 40639.5 | 98509.7037 | 805250 | 0.33278 |
| train | SE | 54 | 26 | 26 | 28 | 0 | 3318 | 40440.0 | 48040.03846 | 158077 | 0.33114 |
| train | OD | 54 | 54 | 54 | 0 | 0 | 122675 | 216130.0 | 220487.66667 | 337365 | 1.76978 |
| test | MA | 27 | 27 | 27 | 0 | 0 | 689 | 10767.0 | 11996.14815 | 25490 | 0.08817 |
| test | HE | 27 | 27 | 27 | 0 | 0 | 2795 | 64753.0 | 130241.44444 | 1186642 | 0.53023 |
| test | EX | 27 | 27 | 27 | 0 | 0 | 6964 | 68089.0 | 132515.55556 | 917148 | 0.55755 |
| test | SE | 27 | 14 | 14 | 13 | 0 | 2832 | 26723.0 | 42563.71429 | 175600 | 0.21882 |
| test | OD | 27 | 27 | 27 | 0 | 0 | 148371 | 208222.0 | 211433.11111 | 282939 | 1.70503 |

| mask_type | masks | empty_masks | positive_pixels_min | positive_pixels_median | positive_pixels_mean | positive_pixels_max | image_percent_median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EX | 81 | 0 | 2343 | 52629.0 | 109844.98765 | 917148 | 0.43095 |
| HE | 80 | 0 | 2149 | 58861.0 | 125212.55 | 1821322 | 0.48198 |
| MA | 81 | 0 | 689 | 10367.0 | 12701.96296 | 38066 | 0.08489 |
| OD | 81 | 0 | 122675 | 214117.0 | 217469.48148 | 337365 | 1.7533 |
| SE | 40 | 0 | 2832 | 38471.0 | 46123.325 | 175600 | 0.31502 |

| mask_type | count | min | median | mean | max |
| --- | --- | --- | --- | --- | --- |
| EX | 11642 | 5 | 217.0 | 764.254 | 376764 |
| HE | 1900 | 89 | 1607.5 | 5272.107 | 1256545 |
| MA | 3497 | 13 | 234.0 | 294.212 | 2231 |
| OD | 81 | 122675 | 214117.0 | 217469.481 | 337365 |
| SE | 150 | 824 | 8653.0 | 12299.553 | 60776 |

Per-mask metadata records exact dtype, dimensions, unique values, binary status, empty status and counts. Correspondence is split-aware within segmentation; missing image/type combinations are explicit in idrid_missing_masks.csv. Missing masks are not assumed negative. Coverage is not population lesion prevalence. OD is anatomy, not a lesion class.

Area percentages use the **full image canvas**, not a validated retinal-area denominator. Eight-connected components are geometric annotation regions, not independent clinical lesion counts. Pixel accuracy can be misleading under sparse foreground. Dice/Focal/Tversky remain future hypotheses; no loss is selected.

## 9. Resolution and small-lesion risk

All operations were in memory; target sizes mean **width**, preserving aspect ratio with rounded height. No square warp/crop is implied. Original eight-connected component IDs are nearest-neighbor sampled, simultaneously preserving binary sampling semantics and identifying which source components survive. Retained source IDs count original regions sampled at least once; disappearance is exact for this interpolation. Target regions may merge or fragment; merger_proxy=max(0,retained IDs−target components) is only a net topology proxy.

| mask_type | target_width | original_positive_pixels | resized_positive_pixels | equivalent_pixels | original_components | retained_components | disappeared_components | resized_components | merger_proxy | components_retained_percent | area_relative_to_expected_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EX | 224 | 8897444 | 24389 | 8923895.348 | 11642 | 7019 | 4623 | 5013 | 2006 | 60.29 | 100.297 |
| EX | 384 | 8897444 | 71328 | 8895767.09 | 11642 | 10129 | 1513 | 8108 | 2021 | 87.004 | 99.981 |
| EX | 512 | 8897444 | 126723 | 8889991.165 | 11642 | 11108 | 534 | 9368 | 1741 | 95.413 | 99.916 |
| EX | 1024 | 8897444 | 507413 | 8899128.585 | 11642 | 11633 | 9 | 10826 | 807 | 99.923 | 100.019 |
| EX | 2048 | 8897444 | 2029067 | 8896563.618 | 11642 | 11642 | 0 | 11366 | 276 | 100.0 | 99.99 |
| HE | 224 | 10017004 | 27384 | 10019760.966 | 1900 | 1829 | 71 | 1764 | 84 | 96.263 | 100.028 |
| HE | 384 | 10017004 | 80468 | 10035674.437 | 1900 | 1892 | 8 | 1839 | 56 | 99.579 | 100.186 |
| HE | 512 | 10017004 | 142857 | 10021838.718 | 1900 | 1899 | 1 | 1858 | 45 | 99.947 | 100.048 |
| HE | 1024 | 10017004 | 570783 | 10010526.556 | 1900 | 1900 | 0 | 1881 | 20 | 100.0 | 99.935 |
| HE | 2048 | 10017004 | 2284341 | 10015827.488 | 1900 | 1900 | 0 | 1895 | 6 | 100.0 | 99.988 |
| MA | 224 | 1028859 | 2832 | 1036224.184 | 3497 | 2257 | 1240 | 2170 | 87 | 64.541 | 100.716 |
| MA | 384 | 1028859 | 8265 | 1030780.549 | 3497 | 3300 | 197 | 3226 | 74 | 94.367 | 100.187 |
| MA | 512 | 1028859 | 14673 | 1029354.106 | 3497 | 3450 | 47 | 3391 | 59 | 98.656 | 100.048 |
| MA | 1024 | 1028859 | 58658 | 1028757.806 | 3497 | 3495 | 2 | 3475 | 20 | 99.943 | 99.99 |
| MA | 2048 | 1028859 | 234603 | 1028630.654 | 3497 | 3497 | 0 | 3490 | 7 | 100.0 | 99.978 |
| SE | 224 | 1844933 | 5056 | 1849982.159 | 150 | 150 | 0 | 148 | 3 | 100.0 | 100.274 |
| SE | 384 | 1844933 | 14865 | 1853908.392 | 150 | 150 | 0 | 148 | 2 | 100.0 | 100.486 |
| SE | 512 | 1844933 | 26242 | 1840953.482 | 150 | 150 | 0 | 148 | 2 | 100.0 | 99.784 |
| SE | 1024 | 1844933 | 105276 | 1846355.259 | 150 | 150 | 0 | 150 | 0 | 100.0 | 100.077 |
| SE | 2048 | 1844933 | 421045 | 1846096.57 | 150 | 150 | 0 | 150 | 0 | 100.0 | 100.063 |

Raw positive pixels across grids are not directly comparable; area_relative_to_expected_percent corrects for geometric scale. Small components can disappear despite stable total normalized area. This establishes annotation sampling risk, not human/model visibility or diagnostic performance. Tiles, multiscale inputs or larger views remain hypotheses; no final resolution is selected.

## 10–11. Visual audit and image characteristics

Deterministic grade grids show up to six images per grade with split/ID, DR and DME. Four segmentation rows span both splits with original/MA/HE/EX/SE views: MA magenta, HE cyan, EX yellow, SE green. OD/fovea overlays, distributions and resolution plots are under outputs/figures/idrid_audit. Tiny lesions may disappear in reduced figures; raw-resolution review remains necessary. Figures enable manual inspection; no independent medical diagnoses or completed ophthalmologist review are claimed.

Full-resolution pixel/RGB moments are in metadata. Brightness/contrast/black fraction/Laplacian variance use fixed 512×340 bilinear RGB proxy views. Gray is arithmetic RGB mean; black means maximum channel ≤15; foreground bbox is in proxy coordinates. This is not a validated retinal FOV mask. Laplacian uses scipy default reflect boundary handling. The fixed view has a slight aspect approximation solely for descriptive proxies. IQR fences Q1−1.5IQR/Q3+1.5IQR flag outliers for review, not clinical gradability. Pigmentation/pathology/content as well as exposure and blur can change these statistics.

## 12. Localization

| split | anatomy | rows | in_bounds |
| --- | --- | --- | --- |
| test | OD | 103 | 103 |
| test | fovea | 103 | 103 |
| train | OD | 413 | 413 |
| train | fovea | 413 | 413 |

Local CSVs provide OD/fovea X/Y centers. OD region masks belong to segmentation, not the localization package. Bounds and bidirectional coverage are checked. Both candidate coordinate-origin bounds are recorded; bounds alone cannot establish indexing. Plotted overlays assume x horizontal, y vertical, top-left origin for inspection. Anatomy could support macular proximity descriptions and spatial reasoning; physical distance needs calibration, and grading improvement is not guaranteed.

## 13–14. Cross-task identity and leakage

| grading_available | segmentation_available | localization_image_available | unique_content_groups |
| --- | --- | --- | --- |
| False | True | False | 78 |
| True | False | True | 507 |
| True | True | True | 3 |

The mapping joins by decoded content, then retrieves grading labels by matched grading split/ID. It retains all task/split/ID records and lesion/anatomy availability. Identical names are insufficient. Intentional cross-task shared supervision is not automatic leakage, but test image reuse through another task would leak information. Exact cross-split decoded groups: 1.

Near-duplicate candidates: 0. The final exhaustive grading-image screen uses 64×64 grayscale correlation ≥0.995 and RGB mean absolute error ≤5/255; false positives/negatives are possible. This replaces an intentionally loose initial mean-threshold hash screen. This cannot exclude arbitrary preprocessing-derived or patient-related duplicates. No patient/eye/visit linkage was found. **Patient-level leakage cannot be fully audited from the publicly available identifiers.**

## 15–16. Provenance and representativeness

**Verified local:** image dimensions/formats above, local LICENSE.txt/CC-BY-4.0.txt, organizer-named partitions and annotation schemas. No row-level demographics found.

**Documentation:** [official data page](https://idrid.grand-challenge.org/Data/) describes a Nanded clinic, Kowa VX-10 alpha, 50-degree macula-centered images and lesion mask totals. [Primary 2018 descriptor](https://www.mdpi.com/2306-5729/3/3/25) reports 2009–2017 examinations at Eye Clinic, Sushrusha Hospital Building; mydriasis with 0.5% tropicamide. Trained student pixel markings underwent two retinal specialists’ consensus review; student center locations were averaged and retinal-expert checked; experts supplied grades. [Organizer page](https://idrid.grand-challenge.org/) records the 2018 challenge context. These are source-reported facts, not independently verified acquisition history here.

**Unknown:** patient counts/linkage, age, sex, ethnicity, residence/rural status, diabetes duration, comorbidities and distributions; quantified annotator agreement and uncertainty.

**Interpretation:** selected single-clinic/camera, mydriatic adequate-quality images cannot establish representation of India broadly, rural screening, multiple hospitals/cameras/protocols or ungradable real-world photographs. Do not infer demographics from location.

## 17–19. Splits, external validation and suitability

Official/local counts are above. No official validation split was found and no test images were merged into training. Prespecify training-only validation and cross-task identity protection. Small correlated samples constrain effective size; scratch-training sufficiency cannot be established by file counts. Fine-tuning is a plausible hypothesis to test, not an architecture choice. Multi-task gains need controlled evaluation.

IDRiD test remains internal if IDRiD is used for training/fine-tuning. Require an independent licensed source, institutions/cameras/protocols/populations relevant to intended use, compatible adjudicated labels, adequate per-class size, patient/visit groups and documented absence of overlap. No external dataset was downloaded. Calibration, abstention, referral benefit and prospective clinical utility need separate evidence.

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

## Integrity checks and failed/uncertain findings

| check | status | detail |
| --- | --- | --- |
| archive_crc:A. Segmentation.zip | PASS | all members CRC valid |
| archive_crc:B. Disease Grading.zip | PASS | all members CRC valid |
| archive_crc:C. Localization.zip | PASS | all members CRC valid |
| grading_bidirectional_correspondence | PASS | {'both': 516, 'left_only': 0, 'right_only': 0} |
| grading_valid_values | PASS | DR 0..4; DME 0..2; missing invalid |
| grading_unique_split_ids | PASS | 516 |
| mask_correspondence | PASS | 363 |
| binary_masks | PASS | {'[0, 1]': 362, '[0, 255]': 1} |
| localization_bounds | PASS | 1032 nonblank annotations; export padding excluded |
| localization_unique_keys | PASS | 1032 nonblank annotations |
| localization_coverage | PASS | nonblank annotation correspondence; padding is not orphan ground truth |
| cross_split_content_duplicates | FAIL | 1 |
| zero_byte_files | PASS | 0 |
| unexpected_files | PASS | [] |
| patient_level_leakage | UNKNOWN | Patient-level leakage cannot be fully audited from the publicly available identifiers. |
| near_duplicate_screen | PASS | 0 nonexact grading pairs with 64x64 grayscale correlation >=0.995 and RGB MAE <=5/255; cannot exclude arbitrary transforms or patient dependencies |
| raw_immutability | PASS | before/after path, size, mtime_ns and SHA-256 comparison |
| git_tracked_dataset_images | UNKNOWN | fatal: not a git repository (or any of the parent directories): .git |
| figures_exist | PASS | 19 |
| csv_reopen | PASS | all generated idrid_*.csv reopened with pandas |
| archive_extraction_correspondence | PASS | 1488 archive members compared with extracted files by path, size, CRC32 |
| content_label_consistency | FAIL | [{'content_sha256': '0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746', 'split': 'train', 'image_id': 'IDRiD_118', 'DR_grade': 0, 'DME_label': 0, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_118.jpg'}, {'content_sha256': '0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746', 'split': 'test', 'image_id': 'IDRiD_064', 'DR_grade': 3, 'DME_label': 0, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\b. Testing Set\\IDRiD_064.jpg'}, {'content_sha256': '11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d', 'split': 'train', 'image_id': 'IDRiD_028', 'DR_grade': 4, 'DME_label': 2, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_028.jpg'}, {'content_sha256': '11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d', 'split': 'train', 'image_id': 'IDRiD_327', 'DR_grade': 3, 'DME_label': 2, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_327.jpg'}, {'content_sha256': '7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c', 'split': 'train', 'image_id': 'IDRiD_045', 'DR_grade': 2, 'DME_label': 0, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_045.jpg'}, {'content_sha256': '7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c', 'split': 'train', 'image_id': 'IDRiD_333', 'DR_grade': 2, 'DME_label': 1, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_333.jpg'}, {'content_sha256': 'e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c', 'split': 'train', 'image_id': 'IDRiD_021', 'DR_grade': 1, 'DME_label': 0, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_021.jpg'}, {'content_sha256': 'e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c', 'split': 'train', 'image_id': 'IDRiD_391', 'DR_grade': 2, 'DME_label': 0, 'path': 'data\\raw\\IDRiD\\original\\B. Disease Grading\\B. Disease Grading\\1. Original Images\\a. Training Set\\IDRiD_391.jpg'}] |
| all_annotation_csv_core_integrity | PASS | No missing core values, duplicate nonblank rows/IDs or nonblank extra fields after excluding all-blank export padding |
| published_total_comparison | PASS | {"observed": {"grading": 516, "grading_train": 413, "grading_test": 103, "segmentation": 81, "MA": 81, "HE": 80, "EX": 81, "SE": 40, "OD": 81}, "documented": {"grading": 516, "grading_train": 413, "grading_test": 103, "segmentation": 81, "MA": 81, "HE": 80, "EX": 81, "SE": 40, "OD": 81}, "source": "https://idrid.grand-challenge.org/Data/ and 2018 descriptor"} |
| extracted_files_not_in_archives | PASS | [] |
| preprocessing_derived_file_scope | PASS | 0 files in interim/processed/external; [] |
| original_format_copies_in_output_code | PASS | [] |
| cross_task_approximate_identity | REVIEW | {'high_similarity_candidate': 47, 'unresolved_candidate': 31, 'verified_exact': 3}; approximate matches are candidates, not confirmed identity |
| raw_immutability_including_supplemental_audits | PASS | Every raw path, byte count, mtime_ns and SHA-256 compared again after supplementary analysis |

PASS applies only to the named definition. UNKNOWN/REVIEW are unresolved results. Raw before/after manifests compare path set, bytes, size and mtime_ns. Access times are not covered. All CSVs are reopened and plot presence checked. Original JPEG/TIFF files were not copied into generated code/output folders; figures are derived annotated thumbnails. Git evidence is unknown when the folder is not a repository.

## 20. All 28 required questions

### 1. What exactly does one sample represent?

A deidentified fundus photograph plus available annotations; not a verified independent patient or visit.

### 2. How many grading images exist?

516

### 3. Official/local train and test counts?

      component split  images
Disease Grading  test     103
Disease Grading train     413
   Localization  test     103
   Localization train     413
   Segmentation  test      27
   Segmentation train      54

### 4. Actual DR distributions?

Exact counts and percentages by split/all are in section 3–5 and idrid_grading_distribution.csv.

### 5. How imbalanced?

split   n majority_grades minority_grades  max_min_ratio  majority_baseline_accuracy  entropy_bits
  all 516          [0, 2]             [1]           6.72                    0.325581      2.078636
 test 103             [0]             [1]           6.80                    0.330097      2.090387
train 413             [2]             [1]           6.80                    0.329298      2.075446

### 6. What DME information exists?

Risk labels and DR cross-tabs; photographic exudate-proximity risk, not OCT thickening.

### 7. How many pixel-annotated images?

81 segmentation images; type coverage differs.

### 8. Which lesions?

MA, HE, EX, SE; OD is separate anatomy.

### 9. Masks for every lesion/image?

No; explicit absent combinations in idrid_missing_masks.csv. Absence is not a verified negative.

### 10. How sparse?

mask_type  masks  empty_masks  positive_pixels_min  positive_pixels_median  positive_pixels_mean  positive_pixels_max  image_percent_median
       EX     81            0                 2343                 52629.0          109844.98765               917148               0.43095
       HE     80            0                 2149                 58861.0          125212.55000              1821322               0.48198
       MA     81            0                  689                 10367.0           12701.96296                38066               0.08489
       OD     81            0               122675                214117.0          217469.48148               337365               1.75330
       SE     40            0                 2832                 38471.0           46123.32500               175600               0.31502

### 11. How tiny are MAs?

mask_type  count  min  median    mean  max
       MA   3497   13   234.0 294.212 2231; geometric pixel areas, not physical lesion sizes.

### 12. Does aggressive resizing destroy MA information?

 target_width  retained_components  disappeared_components  components_retained_percent
          224                 2257                    1240                       64.541
          384                 3300                     197                       94.367
          512                 3450                      47                       98.656
         1024                 3495                       2                       99.943
         2048                 3497                       0                      100.000; sampling evidence, not model performance.

### 13. What anatomy annotations?

1032 center rows plus 81 OD masks.

### 14. Which task images overlap?

3 grading/segmentation content groups; all exact identities/splits in idrid_cross_task_mapping.csv.

### 15. Can overlap support multi-task learning?

Potentially, using partial supervision and content-group split guards. Benefit is unproven.

### 16. Are images duplicated?

1113 file instances / 588 unique decoded groups; cross-task repeats are expected.

### 17. Is there train/test leakage?

1 exact cross-split decoded groups. Other leakage is not ruled out.

### 18. Can patient leakage be ruled out?

No. Patient-level leakage cannot be fully audited from the publicly available identifiers.

### 19. What camera/domain?

Documented Nanded eye clinic, Kowa VX-10 alpha, 50-degree, mydriatic macula-centered photography.

### 20. What demographics are available?

Clinic/population context reported by authors; no local row-level demographic columns.

### 21. What demographics are missing?

Patient count, age/sex/ethnicity, residence, disease duration and distributions, eye/visit linkage.

### 22. Representative of rural India?

Not established; no rural screening sampling frame or domain evidence.

### 23. Enough for scratch deep training?

Not established. Small, imbalanced and potentially correlated samples limit claims; require learning curves and locked evaluation.

### 24. Is fine-tuning more defensible?

A plausible future hypothesis with limited labels; benefit and pretraining overlap need evaluation.

### 25. Can IDRiD alone validate generalization?

It cannot establish external generalization after IDRiD training.

### 26. Exact project role?

Internal expert-annotated grading/lesion/anatomy research benchmark with protected test.

### 27. Additional data needed?

Independent source/camera/population, compatible labels, adequate rare classes, patient linkage, quality targets, license and overlap audit.

### 28. Disclosures to judges?

Small selected single domain; no patient-leakage exclusion; absent-mask ambiguity; photographic DME proxy; tiny-lesion resizing risk; no external/prospective validation. Research decision support only.

## Questions to resolve before model selection

1. What intended-use population, capture workflow, grading standard and human-review/referral policy will be adopted?
2. Can authors clarify patient/eye/visit linkage, absent-mask semantics and coordinate origin?
3. What independent dataset supplies compatible labels, relevant quality/camera variation and rare-grade sample size?
4. How will training-only validation and cross-task content protection be prespecified and final test locked?
5. What resolution/tiles/multiscale hypotheses preserve tiny MA signals, separately from predictive performance?
6. How will ordinal errors, class imbalance, missing supervision and DME proxy meaning be evaluated before choosing losses?
7. How will calibration, abstention, quality and explanation fidelity be validated with suitable targets and human reviewers?
8. What learning curves and confidence intervals would justify capacity, fine-tuning or multi-task complexity?

## Reproduce and review

From D:\DR_Hackathon run `.venv\Scripts\python.exe src\data\audit_idrid.py`. Install with `.venv\Scripts\python.exe -m pip install -r requirements-audit.txt`. The driver discovers actual files and regenerates reports/tables/figures; no notebook edits needed. Versions/platform/seed are recorded in idrid_environment.json.

Review IDRiD_LIMITATIONS.md, IDRiD_SUITABILITY_MATRIX.md, idrid_integrity_checks.csv, idrid_resolution_summary.csv, idrid_cross_task_mapping.csv, idrid_missing_masks.csv, idrid_quality_outliers.csv and the figures. Exact paths/headers are in inventory/schema CSVs.
