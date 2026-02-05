> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 48-A

## Goal
Make torso method tracking visible in facts_summary.json (no extra noisy outputs), so we can prove whether alpha/cluster paths are executed or not.

## Changes
- **Method Tracking Wiring Fix**:
  - core_measurements_v0: Ensured TORSO_METHOD_USED is recorded for ALL SINGLE_COMPONENT_ONLY cases
  - Fixed method assignment logic to ensure exactly one method label per case: alpha_shape, cluster_trim, or single_component_fallback
  - Added tracking_missing warning if method is not set (should not happen)
  - Method is recorded even if perimeter computation fails (records attempted method)
- **Runner Aggregation**:
  - Round48-A: Verify sum of torso_method_used_count equals processed_cases
  - Record torso_method_tracking_missing_count if sum mismatch detected
  - Ensure facts_summary contains top-level TORSO_METHOD_USED section with counts

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round48_20260127_205355`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round48_20260127_205355/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round48_20260127_205355/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round48_20260127_205355/KPI_DIFF.md`

## PR Link
[Round48-A PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
- **Failure Reasons TopK**: `SINGLE_COMPONENT_ONLY=20` (all 20 processed cases; unchanged from Round47)
- **TORSO_METHOD_USED Counts**:
  - alpha_shape: 20 (all 20 cases used alpha-shape-like concave boundary method)
  - cluster_trim: 0
  - single_component_fallback: 0
  - Sum: 20 (equals processed_cases, tracking complete)
- **TORSO_METHOD_USED by Key**: NECK_CIRC_M: alpha_shape=20
- **Method Tracking Verification**: All 20 processed cases have method labels recorded (no missing tracking)
- **Torso Delta Stats (Full - Torso)**:
  - BUST_CIRC_M: p50=-0.778m, p95=-0.477m
  - UNDERBUST_CIRC_M: p50=-0.653m, p95=-0.646m
- **Torso Diagnostics Summary**: Present with `n_intersection_points_summary`, `n_segments_summary`, `n_components_summary` for NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M
