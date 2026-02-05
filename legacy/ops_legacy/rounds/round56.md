> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 56

## Goal
Refine ALPHA_FAIL:TOO_FEW_POINTS into stage-specific codes and add missing diagnostics fields (facts-only). No algorithm tuning.

## Changes
- **Stage-Specific Failure Codes**:
  - Round56: Replace ambiguous TOO_FEW_POINTS code with stage-specific codes:
    - ALPHA_FAIL:TOO_FEW_SLICE_POINTS (if vertices_2d has < 3 points)
    - ALPHA_FAIL:TOO_FEW_COMPONENT_POINTS (if single_comp has < 3 points)
    - ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS (if alpha_boundary is None or len < 3)
  - Ensure exactly one reason per fallback case
- **Expanded Diagnostics**:
  - Round56: For fallback cases, record per-case:
    - n_slice_points_raw
    - n_slice_points_after_dedupe
    - n_component_points
    - n_boundary_points
    - n_loops_found
    - slice_thickness_used
    - slice_plane_level
  - Store in torso_diagnostics["too_few_points_diagnostics"]
- **Aggregation into facts_summary.json**:
  - Round56: Aggregate too_few_points_diagnostics_summary (min/p50/p95/max/count) for each field
  - Updated to handle all stage-specific failure codes (TOO_FEW_SLICE_POINTS, TOO_FEW_COMPONENT_POINTS, TOO_FEW_BOUNDARY_POINTS)
  - Always emit empty dict to avoid missing key confusion

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round56_20260127_225000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round56_20260127_225000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round56_20260127_225000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round56_20260127_225000/KPI_DIFF.md`

## PR Link
[Round56 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - [counts from facts_summary]
- **Alpha Fail Reasons TopK** (alpha_fail_reasons_topk) - stage-specific:
  - [reason]: [count] (e.g., ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS: 2)
- **Too Few Points Diagnostics Summary** (too_few_points_diagnostics_summary):
  - n_slice_points_raw: {min, p50, p95, max, count}
  - n_slice_points_after_dedupe: {min, p50, p95, max, count}
  - n_component_points: {min, p50, p95, max, count}
  - n_boundary_points: {min, p50, p95, max, count}
  - n_loops_found: {min, p50, p95, max, count}
  - slice_thickness_used: {min, p50, p95, max, count}
  - slice_plane_level: {min, p50, p95, max, count}
- **Failure Reasons TopK Overall**: [from facts_summary]
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
