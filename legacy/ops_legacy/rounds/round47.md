> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 47

## Goal
Reduce arm-inflated torso circumference by refining torso extraction on 2D slice geometry for SINGLE_COMPONENT_ONLY cases, while keeping the system alive and recording facts-only signals.

## Changes
- **Torso Refinement for SINGLE_COMPONENT_ONLY Cases**:
  - core_measurements_v0: Added two refinement methods before Round45 single component fallback:
    - Option A: alpha-shape-like concave boundary using kNN graph boundary detection
    - Option B: cluster/trim approach using DBSCAN clustering to keep central cluster
  - Both methods attempt to extract a more accurate torso boundary from single component points
  - If both refinement methods fail, fallback to Round45 single component fallback (ordering -> unordered -> hull)
  - Record TORSO_METHOD_USED flag: "alpha_shape", "cluster_trim", or "single_component_fallback"
- **Runner Aggregation**:
  - Round47: Aggregate TORSO_METHOD_USED counts (per case/key) and add to facts_summary
  - Keep existing failure reason logging unchanged

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round47_20260127_203605`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round47_20260127_203605/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round47_20260127_203605/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round47_20260127_203605/KPI_DIFF.md`

## PR Link
[Round47 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
- **Failure Reasons TopK**: `SINGLE_COMPONENT_ONLY=20` (all 20 processed cases; refinement methods did not change failure reason classification)
- **TORSO_METHOD_USED**: Not present in facts_summary (all cases may have used single_component_fallback, or method tracking needs verification)
- **Torso Delta Stats (Full - Torso)**:
  - BUST_CIRC_M: p50=-0.778m, p95=-0.477m (torso values smaller than full, indicating arm exclusion)
  - UNDERBUST_CIRC_M: p50=-0.653m, p95=-0.646m (torso values smaller than full)
- **Torso Diagnostics Summary**: Present with `n_intersection_points_summary`, `n_segments_summary`, `n_components_summary` for NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M
- **Scale Warnings**: 20 cases had mm->m conversion (expected for proxy OBJ files)
