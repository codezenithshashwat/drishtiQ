# IDRiD experimental data policy — IDRID_PRIMARY_C_PLUS_D_V1

**Patient-level leakage cannot be fully audited from the publicly available identifiers. Zero exact-image overlap is not proof of patient independence.**

## Primary protocol and permissions

Use only `data/interim/manifests/idrid_grading_train_clean.csv` as the model-development pool and `idrid_grading_test_clean.csv` as the held-out internal test. These contain 404 / 102 rows. Do not glob raw folders to obtain training data. No sample was moved between organizer partitions. A future validation partition must be prespecified within the clean training pool; this stage does not assign it. Test data must not guide tuning, early stopping, preprocessing choice or model selection. The test labels have been inspected for audit purposes; disclose this and avoid iterative outcome-driven test reuse.

Primary policy combines **C + D**: quarantine every member of any exact-content group whose DR OR DME labels disagree; then retain one canonical sample only for groups where BOTH labels agree. Even a DME-only conflict is quarantined for the primary grading protocol, rather than permitting task-specific inconsistent inclusion. No clinical label has been selected, repaired, averaged or inferred. Quarantine is a manifest permission, not deletion. Any exact image alias in localization/segmentation inherits the content-level prohibition; excluded content may not re-enter through auxiliary supervision, pretraining, augmentation or validation.

Canonical order is deterministic: prefer official test over train if an agreeing group ever spans partitions, then lexicographically smallest image ID, then normalized raw-relative filepath. Prioritizing test in that hypothetical case protects the original holdout; no such agreeing cross-split group exists here. Current agreeing groups keep train IDRiD_073 and IDRiD_079; train IDRiD_375 and IDRiD_279 are redundant exclusions. This selects a representation of identical pixels with identical labels, not the clinically correct label. Canonical localization annotations, if used later, must come from the same retained split/ID verified by content; do not average repeated centers automatically.

`sample_key` = `idrid:grading:<original_split>:<image_id>`. `filepath` is project-root-relative with forward slashes; resolve against the project root, not the current shell directory. `content_hash` is the audit's SHA-256 over mode/size plus decoded pixels; `file_sha256` hashes original bytes. Labels and official assignments are preserved. Duplicate group IDs contain the full decoded hash. Manifest rows are sorted deterministically. Primary inclusion/exclusion is explicit and all 516 official rows are accounted for.

## Exact changes and exclusions

| policy | train | test | excluded | unique_contents | exact_cross_split_groups | known_conflicting_content_groups_still_included | remaining_duplicate_groups |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A_official_unchanged | 413 | 103 | 0 | 510 | 1 | 4 | 6 |
| B_drop_test_overlap | 413 | 102 | 1 | 510 | 0 | 4 | 5 |
| C_quarantine_all_conflicting_groups | 406 | 102 | 8 | 506 | 0 | 0 | 2 |
| D_deduplicate_agreeing_groups_only | 411 | 103 | 2 | 510 | 1 | 4 | 4 |
| PRIMARY_C_plus_D | 404 | 102 | 10 | 506 | 0 | 0 | 0 |

| original_split | exclusion_reason | count |
| --- | --- | --- |
| test | conflicting_DR_or_DME_labels_all_group_members_quarantined | 1 |
| train | conflicting_DR_or_DME_labels_all_group_members_quarantined | 7 |
| train | redundant_exact_duplicate_labels_agree | 2 |

Excluded rows with original labels, paths, group and rationale:

| sample_key | DR_grade | DME_label | duplicate_status | exclusion_reason |
| --- | --- | --- | --- | --- |
| idrid:grading:test:IDRiD_064 | 3 | 0 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_021 | 1 | 0 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_028 | 4 | 2 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_045 | 2 | 0 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_118 | 0 | 0 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_279 | 1 | 0 | agreeing_duplicate_noncanonical | redundant_exact_duplicate_labels_agree |
| idrid:grading:train:IDRiD_327 | 3 | 2 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_333 | 2 | 1 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |
| idrid:grading:train:IDRiD_375 | 2 | 1 | agreeing_duplicate_noncanonical | redundant_exact_duplicate_labels_agree |
| idrid:grading:train:IDRiD_391 | 2 | 0 | conflicting_labels | conflicting_DR_or_DME_labels_all_group_members_quarantined |

## Candidate policy comparison

- **A — official unchanged:** maximum benchmark faithfulness and full sample size; leaves exact train/test leakage and all annotation contradictions. Reproducible but scientifically compromised as an independent primary evaluation.
- **B — remove overlapping test photographs:** removes exact train/test overlap by dropping the overlapping test row. It leaves conflicting training duplicate groups and a train-side member whose held-out alias disagreed; it does not adjudicate that remaining label. The smaller test is no longer the official benchmark, and training still contains redundant images.
- **C — quarantine all conflicting groups:** removes contradictions without choosing labels and blocks the observed cross-split duplicate. Same-label training duplicates remain, overweighting identical photographs and risking leakage if a later validation split ignores content.
- **D — deduplicate agreeing groups only:** reduces redundant sample weighting reproducibly but, as a stand-alone policy, leaves conflicting groups unchanged and does not fix the exact train/test conflict. It is not sufficient for primary experiments. D is never permission to pick a winner in a conflicting group.
- **C + D — recommended primary:** removes the eight conflicting rows and two redundant agreeing rows, yielding a content-unique, exact-overlap-free primary set. Costs 10 rows and departs from published official sample counts. It is conservative and traceable but cannot repair labels, establish patient independence or guarantee labels in singleton groups are correct.

All alternatives preserve immutable raw data; each candidate's train/test/excluded and remaining risk counts are computed in idrid_duplicate_policy_comparison.csv. The unchanged official manifest is available only as a separately labeled **secondary official comparison with known duplicate/leakage/label-conflict caveats**. It is not an additional primary training pool. Never report its scores as leakage-free, combine its results with the clean test, or choose a policy because it improves observed performance. Preserve the same fitting procedure for any later comparisons and disclose differing evaluation counts.

## Class and DME distributions

| stage | split | target | label | count | percent | total |
| --- | --- | --- | --- | --- | --- | --- |
| official | train | DR_grade | 0 | 134 | 32.445520581113804 | 413 |
| official | train | DR_grade | 1 | 20 | 4.842615012106537 | 413 |
| official | train | DR_grade | 2 | 136 | 32.92978208232446 | 413 |
| official | train | DR_grade | 3 | 74 | 17.91767554479419 | 413 |
| official | train | DR_grade | 4 | 49 | 11.864406779661017 | 413 |
| official | train | DME_label | 0 | 177 | 42.857142857142854 | 413 |
| official | train | DME_label | 1 | 41 | 9.927360774818402 | 413 |
| official | train | DME_label | 2 | 195 | 47.21549636803874 | 413 |
| official | test | DR_grade | 0 | 34 | 33.00970873786408 | 103 |
| official | test | DR_grade | 1 | 5 | 4.854368932038835 | 103 |
| official | test | DR_grade | 2 | 32 | 31.06796116504854 | 103 |
| official | test | DR_grade | 3 | 19 | 18.446601941747574 | 103 |
| official | test | DR_grade | 4 | 13 | 12.62135922330097 | 103 |
| official | test | DME_label | 0 | 45 | 43.689320388349515 | 103 |
| official | test | DME_label | 1 | 10 | 9.70873786407767 | 103 |
| official | test | DME_label | 2 | 48 | 46.601941747572816 | 103 |
| official | all | DR_grade | 0 | 168 | 32.55813953488372 | 516 |
| official | all | DR_grade | 1 | 25 | 4.844961240310078 | 516 |
| official | all | DR_grade | 2 | 168 | 32.55813953488372 | 516 |
| official | all | DR_grade | 3 | 93 | 18.023255813953487 | 516 |
| official | all | DR_grade | 4 | 62 | 12.015503875968992 | 516 |
| official | all | DME_label | 0 | 222 | 43.02325581395349 | 516 |
| official | all | DME_label | 1 | 51 | 9.883720930232558 | 516 |
| official | all | DME_label | 2 | 243 | 47.093023255813954 | 516 |
| clean | train | DR_grade | 0 | 133 | 32.92079207920792 | 404 |
| clean | train | DR_grade | 1 | 18 | 4.455445544554455 | 404 |
| clean | train | DR_grade | 2 | 132 | 32.67326732673268 | 404 |
| clean | train | DR_grade | 3 | 73 | 18.06930693069307 | 404 |
| clean | train | DR_grade | 4 | 48 | 11.881188118811881 | 404 |
| clean | train | DME_label | 0 | 172 | 42.57425742574257 | 404 |
| clean | train | DME_label | 1 | 39 | 9.653465346534654 | 404 |
| clean | train | DME_label | 2 | 193 | 47.77227722772277 | 404 |
| clean | test | DR_grade | 0 | 34 | 33.33333333333333 | 102 |
| clean | test | DR_grade | 1 | 5 | 4.901960784313726 | 102 |
| clean | test | DR_grade | 2 | 32 | 31.372549019607842 | 102 |
| clean | test | DR_grade | 3 | 18 | 17.647058823529413 | 102 |
| clean | test | DR_grade | 4 | 13 | 12.745098039215685 | 102 |
| clean | test | DME_label | 0 | 44 | 43.13725490196079 | 102 |
| clean | test | DME_label | 1 | 10 | 9.803921568627452 | 102 |
| clean | test | DME_label | 2 | 48 | 47.05882352941176 | 102 |
| clean | all | DR_grade | 0 | 167 | 33.00395256916996 | 506 |
| clean | all | DR_grade | 1 | 23 | 4.545454545454546 | 506 |
| clean | all | DR_grade | 2 | 164 | 32.41106719367589 | 506 |
| clean | all | DR_grade | 3 | 91 | 17.984189723320156 | 506 |
| clean | all | DR_grade | 4 | 61 | 12.055335968379447 | 506 |
| clean | all | DME_label | 0 | 216 | 42.68774703557312 | 506 |
| clean | all | DME_label | 1 | 49 | 9.683794466403162 | 506 |
| clean | all | DME_label | 2 | 241 | 47.62845849802372 | 506 |

| stage | split | n | majority_grades | minority_grades | max_min_ratio | majority_percent |
| --- | --- | --- | --- | --- | --- | --- |
| official | train | 413 | [2] | [1] | 6.8 | 32.929782 |
| official | test | 103 | [0] | [1] | 6.8 | 33.009709 |
| official | all | 516 | [0, 2] | [1] | 6.72 | 32.55814 |
| clean | train | 404 | [0] | [1] | 7.388889 | 32.920792 |
| clean | test | 102 | [0] | [1] | 6.8 | 33.333333 |
| clean | all | 506 | [0] | [1] | 7.26087 | 33.003953 |

Interpretation: inspect percentage-point changes as descriptive quantities, not a test of clinical representativeness. Cleaning changes training DR counts from [134,20,136,74,49] to [133,18,132,73,48]; test from [34,5,32,19,13] to [34,5,32,18,13]. Grade 1 remains the smallest class, loses 2/20 training examples, and the training max/min ratio rises from 6.8 to 7.388889. The overall imbalance structure remains, with a modest proportional change but a meaningful 10% reduction of the already rare training grade. No class-weight or sampling decision is made. DME counts and percentages are separate above; DME retains its photographic risk interpretation and is not OCT-confirmed thickening.

## Segmentation annotation availability

The policy table has one row per segmentation image and annotation type (MA, HE, EX, SE, OD), not just rows with files. Available nonempty masks: 363; unavailable image/type combinations: 42; verified empty mask files: 0. MA/EX/OD coverage is 81 each, HE 80, SE 40. An absent mask is **unavailable supervision**, not a negative lesion label. `annotation_available` / `supervision_valid` must gate any future supervised calculation; an unavailable target is null. If a batching interface later needs a placeholder tensor, it must carry validity=false and contribute no supervised loss or segmentation metric; the placeholder never becomes a clinical negative. Only an explicitly supplied readable binary all-zero annotation can be marked verified empty. This rule describes annotation content, not independent clinical adjudication. No such mask was observed.

Preserve palette indices for P masks. For the RGBA EX mask, derive foreground from RGB channels only and exclude opaque alpha. Do not silently grayscale a red mask with a threshold that changes its meaning. OD is anatomical supervision, not a lesion class. Stand-alone segmentation train/test assignments stay organizer-provided; this stage does not authorize mixing all 54 segmentation training images into grading training.

## Cross-task correspondence and safeguards

| correspondence_tier | automatic_multitask_permission | images |
| --- | --- | --- |
| exact_verified_correspondence | True | 3 |
| strongly_supported_candidate_not_verified | False | 47 |
| uncertain_correspondence | False | 31 |

The three exact segmentation/grading matches are eligible automatically only because they map to one permitted clean grading record and share the same organizer partition. They appear in idrid_multitask_exact_clean.csv. The 47 high-similarity cases are strongly supported **candidates**, not verified identity; the 31 uncertain nearest candidates are not mappings. Neither category is merged or receives automatic grading labels for segmentation use. All raw candidate evidence and split discrepancies remain in idrid_cross_task_mapping_review.csv. Thirteen strong candidates and seventeen uncertain candidates point across task partitions. These are unresolved risks, not thirty proven duplicate identities. Restrict combined grading/segmentation experiments to the exact manifest until review resolves correspondence. Any future approval requires explicit documented evidence, a versioned mapping and a new cross-task content/split check. Approximate alternatives may not be silently promoted. Unmapped auxiliary images may not be used for primary grading training merely because their segmentation folder says train.

All localization images can be matched by exact content to grading imagery, but repeated content may have differing center annotations. For future anatomy supervision, select only the permitted clean grading sample's content-verified same-split/ID localization record; quarantine excluded contents and retain the canonical record for agreeing groups. No patient identity is inferred from names, coordinates or visual similarity.

## Raw data, evidence and reproduction

Raw files, ZIPs, labels and split folders are read-only inputs. No copies, moves, relabeling, crops or image derivatives are created in raw. Full path/size/mtime_ns/SHA-256 snapshots bracket this focused stage and are compared with the completed audit snapshot. Access timestamps are not covered. Existing audit artifacts and resolution experiments are consumed, not regenerated. Selective duplicate/archive evidence checks are new focused verification. Input checksums and exact generated artifact hashes are recorded in idrid_integrity_resolution_provenance.json. Manifests are byte-reproducible from the same inputs; two independent in-memory builds are compared, and a second complete invocation is validated separately.

Run from D:\DR_Hackathon: `.venv\Scripts\python.exe src\data\resolve_idrid_integrity.py`. Uses the existing requirements-audit.txt environment; no new model dependency. Generated manifests live in data/interim/manifests, policy reports in docs/dataset_audit, and evidence/checks under outputs/metrics. The interim directory is ignored by the existing .gitignore; code/policy plus source fingerprints provide regeneration even when manifests are not tracked.

## Validation scope, unknowns and external validation

| check | status | detail |
| --- | --- | --- |
| raw_matches_completed_audit | PASS | IDRiD path, size, mtime_ns and bytes agree with final completed audit snapshot |
| two_independent_manifest_builds_identical | PASS | All constructed manifest/policy-table bytes identical for repeated pure builds |
| duplicate_archive_evidence | PASS | 24 duplicate image aliases; both archive grading CSVs also byte-matched |
| six_duplicate_groups_and_four_conflicts_reconciled | PASS | Grouped existing image hashes independently and reconciled audited conflicts |
| zero_clean_train_test_exact_overlap | PASS | 0 |
| zero_within_clean_exact_duplicates | PASS | 506 included rows; 506 content hashes |
| all_included_filepaths_exist | PASS | 506 |
| all_manifest_paths_within_raw | PASS | Included and excluded grading rows reference immutable raw inputs |
| manifest_file_hashes_match_current_raw | PASS | All 516 grading rows checked against the current raw snapshot, not just path existence |
| included_valid_DR_DME_labels | PASS | No missing or out-of-domain included targets |
| included_labels_match_raw_CSV | PASS | checked below against original raw CSV fields |
| no_quarantined_content_included | PASS | All aliases of four conflicting content groups excluded from primary grading |
| no_excluded_key_included | PASS | 0 |
| grading_sample_keys_globally_unique | PASS | 516 |
| official_partition_fully_accounted_for | PASS | Primary included/excluded partition of all official grading rows |
| no_cross_partition_reassignment | PASS | Every clean row retains original split |
| mask_absence_never_negative | PASS | 42 unavailable masks carry null target and validity=false |
| annotation_table_complete | PASS | 405 |
| available_mask_paths_exist | PASS | 363 |
| available_masks_valid_in_completed_audit | PASS | All available masks fully decoded and binary in unchanged audited files |
| multitask_only_exact_permitted_same_split | PASS | 3 |
| multitask_train_no_clean_test_content | PASS | Only permitted exact same-split links; approximate candidates blocked |
| cross_task_candidates_not_auto_merged | PASS | 47 strong candidates and 31 uncertain candidates remain review-only |
| patient_level_independence | UNKNOWN | Patient-level leakage cannot be fully audited from the publicly available identifiers. |
| approximate_cross_task_identity | REVIEW | 47 strong and 31 uncertain candidates unresolved; primary combined use restricted to exact links |
| written_CSVs_reopen_and_match_generated_bytes | PASS | 14 |
| prior_audit_artifacts_unchanged | PASS | 18 |
| raw_unchanged_during_resolution | PASS | All files under data/raw: path, byte count, mtime_ns and SHA-256; access times excluded |

Mechanical checks can pass while patient-level independence remains unknown and approximate cross-task identities remain under review. No patient identifiers are available; patient-level leakage cannot be ruled out. Zero exact overlap does not exclude transformed images, paired eyes, visits or institutions' sampling dependencies. Cleaned labels remain original labels, not re-adjudicated ground truth. Existing singleton errors may remain. Publisher authenticity is not independently established by agreement of local ZIPs and extraction. The clean test is still an internal IDRiD test, not external validation. Independent institutions/cameras/populations and compatible licensed labels with overlap screening remain necessary.

No CNN, Transformer, segmentation model, loss, optimizer, augmentation pipeline, final resolution or referral threshold was selected, and no training was run.
