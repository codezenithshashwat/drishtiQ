# Limitations, risks, unknowns and threats to validity

**Patient-level leakage cannot be fully audited from the publicly available identifiers.** No patient, paired-eye or visit key was found in local CSV schemas. Image serials do not establish independent patients.

- Small and imbalanced training/test strata constrain learning and evaluation precision. No official validation partition was found. Repeated test use for model selection biases final evaluation.
- Adequate-quality, disease-stratified selection cannot establish screening prevalence or performance on ungradable images. No gradability target exists locally.
- One documented clinic/camera domain cannot establish broad Indian, rural, multi-hospital, multi-camera, ethnic or protocol representation. Age, sex, ethnicity, residence, patient counts, diabetes duration and their distributions remain unknown from local annotations.
- Absent HE/SE masks are not explicit empty masks and must not silently become verified negative labels. Boundary uncertainty and inter-rater agreement are not quantified locally.
- Mask encodings differ: one EX mask is RGBA with fully opaque alpha. Treating alpha as foreground yields incorrect areas; downstream loaders must preserve the documented RGB-only semantic interpretation.
- DME labels reflect photographic hard-exudate proximity risk, not OCT-confirmed retinal thickening or clinical DME diagnosis.
- IDs reset across splits/tasks. Filename joins can misassign labels. Auxiliary-task training can leak a grading test image through shared content.
- Exact hashes exclude only byte/decoded-pixel duplicates. Perceptual screening cannot exclude arbitrary crops, transforms, fellow eyes or repeated visits; candidate pairs need review.
- Quality proxies use a fixed 512×340 view and include dark borders. Foreground thresholding is not a validated retinal mask; blur statistics are not clinical gradability labels.
- Nearest-neighbor component sampling is a geometric annotation experiment, not lesion visibility or model performance. Connected regions need not be distinct biological lesions. Component merging/fragmentation and lack of physical pixel calibration limit interpretation.
- CSV headers do not establish zero- versus one-based coordinate origin. Passing bounds under both conventions cannot resolve it; overlays use top-left plotting coordinates for inspection.
- No publisher checksum was supplied. Archive CRC and local hash comparisons establish internal consistency, not authoritative authenticity. Immutability covers paths, sizes, modification timestamps and bytes during this run, not historical provenance or access times.
- CC BY 4.0 requires attribution; licensing does not establish clinical effectiveness or regulatory approval.
- Internal results cannot establish external generalization, uncertainty calibration, referral benefit, explanation faithfulness, prospective workflow safety or autonomous diagnostic validity.

## Verified critical integrity failure

Exact decoded content carries conflicting disease grades across organizer train/test. Do not silently deduplicate, relabel or treat the official test as independent. Resolve provenance and predefine handling before training. Raw files were preserved.

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
