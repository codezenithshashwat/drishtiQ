# IDRiD resolution findings

This note preserves the completed audit experiment; no resizing experiment was rerun and no raw images were modified.

| target_width | original_components | retained_components | disappeared_components | components_retained_percent | components_lost_percent | area_relative_to_expected_percent |
| --- | --- | --- | --- | --- | --- | --- |
| 224 | 3497 | 2257 | 1240 | 64.541 | 35.458965 | 100.716 |
| 384 | 3497 | 3300 | 197 | 94.367 | 5.6334 | 100.187 |
| 512 | 3497 | 3450 | 47 | 98.656 | 1.344009 | 100.048 |
| 1024 | 3497 | 3495 | 2 | 99.943 | 0.057192 | 99.99 |
| 2048 | 3497 | 3497 | 0 | 100.0 | 0.0 | 99.978 |

At width 224 (aspect-preserved height 149), 1,240 of 3,497 original eight-connected MA annotation regions disappeared: **35.458965%**. At that width 1,814 surviving source regions collapsed to one target pixel (see existing idrid_ma_component_topology_summary.csv). Aggregate normalized foreground area remained about 100.716% of expected, illustrating why area alone misses small-component loss.

Method: in-memory nearest-neighbor sampling of binary/component-ID masks; widths 2048, 1024, 512, 384, 224 with proportional rounded heights. Components are geometric annotation regions, not independently diagnosed biological lesions. This is sampling evidence, not predictive performance, clinical visibility or a physical lesion-size measurement.

No final input resolution, crop, augmentation or preprocessing strategy is selected.

**Research question:** What input strategy preserves clinically important small-lesion information while retaining sufficient global retinal context and remaining computationally practical?
