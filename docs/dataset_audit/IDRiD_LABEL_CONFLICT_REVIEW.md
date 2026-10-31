# IDRiD label conflict review

**No clinical label was adjudicated or corrected. Patient-level leakage cannot be fully audited from the publicly available identifiers.**

## Content 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746

| filepath | original_split | image_id | file_sha256 | DR_grade | DME_label |
| --- | --- | --- | --- | --- | --- |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/b. Testing Set/IDRiD_064.jpg | test | IDRiD_064 | 505330878f4d4186a71b8001570100b82b6b05cb431e81e2c259d8c584314708 | 3 | 0 |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_118.jpg | train | IDRiD_118 | 505330878f4d4186a71b8001570100b82b6b05cb431e81e2c259d8c584314708 | 0 | 0 |

Crosses train/test: True. Identical bytes and decoded pixels carry contradictory DR and/or DME labels. All grading members and any exact-content auxiliary aliases are quarantined from primary experiments. This establishes inconsistency, not which annotation is correct. Clinical/source-author review remains unresolved.

## Content 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d

| filepath | original_split | image_id | file_sha256 | DR_grade | DME_label |
| --- | --- | --- | --- | --- | --- |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_028.jpg | train | IDRiD_028 | 350754e96bf6b9540264c1b53088dc1f5826edb2a9d3d3221acf9ef5afd76a13 | 4 | 2 |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_327.jpg | train | IDRiD_327 | 350754e96bf6b9540264c1b53088dc1f5826edb2a9d3d3221acf9ef5afd76a13 | 3 | 2 |

Crosses train/test: False. Identical bytes and decoded pixels carry contradictory DR and/or DME labels. All grading members and any exact-content auxiliary aliases are quarantined from primary experiments. This establishes inconsistency, not which annotation is correct. Clinical/source-author review remains unresolved.

## Content 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c

| filepath | original_split | image_id | file_sha256 | DR_grade | DME_label |
| --- | --- | --- | --- | --- | --- |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_045.jpg | train | IDRiD_045 | fe4f412a179adf78bd9a367d1702878d45302db3f7706c4bf7efc834a312e91c | 2 | 0 |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_333.jpg | train | IDRiD_333 | fe4f412a179adf78bd9a367d1702878d45302db3f7706c4bf7efc834a312e91c | 2 | 1 |

Crosses train/test: False. Identical bytes and decoded pixels carry contradictory DR and/or DME labels. All grading members and any exact-content auxiliary aliases are quarantined from primary experiments. This establishes inconsistency, not which annotation is correct. Clinical/source-author review remains unresolved.

## Content e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c

| filepath | original_split | image_id | file_sha256 | DR_grade | DME_label |
| --- | --- | --- | --- | --- | --- |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_021.jpg | train | IDRiD_021 | 7c8af82fac4906b51dbe2d827e050b8b29a18cac21f569d2ac16af1cd65c9baf | 1 | 0 |
| data/raw/IDRiD/original/B. Disease Grading/B. Disease Grading/1. Original Images/a. Training Set/IDRiD_391.jpg | train | IDRiD_391 | 7c8af82fac4906b51dbe2d827e050b8b29a18cac21f569d2ac16af1cd65c9baf | 2 | 0 |

Crosses train/test: False. Identical bytes and decoded pixels carry contradictory DR and/or DME labels. All grading members and any exact-content auxiliary aliases are quarantined from primary experiments. This establishes inconsistency, not which annotation is correct. Clinical/source-author review remains unresolved.

## Archive evidence

All duplicate image members were selectively reread and decoded from the retained B/C ZIPs. Both original B grading CSVs were reread from ZIP bytes and matched against untouched extracted CSVs. Per-member hashes and original labels are in idrid_duplicate_archive_evidence.csv. All 24 image-member comparisons passed byte identity, decoded identity and label correspondence. The train IDRiD_118 (DR 0, DME 0) / test IDRiD_064 (DR 3, DME 0) conflict therefore exists in these retained archives. This does not establish authenticity against an unavailable publisher checksum.

## All six duplicate groups

| duplicate_group | content_hash | grading_members | DR_labels_agree | DME_labels_agree | labels_agree | crosses_train_test | creates_exact_split_leakage | creates_label_conflict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dup_0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | 0f0ccc64dc53883f16907d7add8a3b53586cd04ffafef0939d99aea769cd6746 | 2 | False | True | False | True | True | True |
| dup_11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | 11dee2a00eb7f688f1409f829d4fbdfc9baf1aa673049b040b1efc16a57c918d | 2 | False | True | False | False | False | True |
| dup_56edb589ae93c14547a7d858a5b4d7d8796e0ed8d16a2343469b68cd2ce340f9 | 56edb589ae93c14547a7d858a5b4d7d8796e0ed8d16a2343469b68cd2ce340f9 | 2 | True | True | True | False | False | False |
| dup_7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | 7d7ea473969b1cb8208953f509f07f3f1e7cc43ab147da2164f5d317e820f72c | 2 | True | False | False | False | False | True |
| dup_964bd06f485fe4ae0a7f917f3af7fd00e2e33896695119e6d17b56620e9fd743 | 964bd06f485fe4ae0a7f917f3af7fd00e2e33896695119e6d17b56620e9fd743 | 2 | True | True | True | False | False | False |
| dup_e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | e922c66bbce5130200ba4d90ae4eeb48f5e79f9414de47532ff8c34e4583706c | 2 | False | True | False | False | False | True |

The row-level resolution CSV includes every B/C image filepath, not only the grading aliases. Same-label groups retain train:IDRiD_073 and train:IDRiD_079 as deterministic canonical samples. The removed duplicate aliases retain their unchanged original labels in the exclusions manifest. No raw files were touched.
