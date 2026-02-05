> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 55

## Goal
Add facts-only diagnostics for ALPHA_FAIL:TOO_FEW_POINTS and apply a minimal geometry-based mitigation (no KPI clamping).

## Changes
- **Diagnostics for TOO_FEW_POINTS**:
  - Round55: When alpha fails with ALPHA_FAIL:TOO_FEW_POINTS, record per-case diagnostics:
    - n_slice_points_raw: Number of points in slice before dedupe/component extraction
    - n_slice_points_after_dedupe: Number of points in selected component after dedupe
    - slice_thickness_used: Tolerance value used for slice (in meters)
    - slice_plane_level: Y-value used for the slice
  - Store in torso_diagnostics["too_few_points_diagnostics"]
- **Aggregation into facts_summary.json**:
  - Round55: Add too_few_points_diagnostics_summary (min/p50/p95/max/count for each field)
  - Always emit empty dict to avoid missing key confusion
- **Minimal Geometry-Based Mitigation**:
  - Round55: Adjust slice_thickness selection to be derived from mesh scale / edge length (deterministic)
  - Compute tolerance as 0.2% of median mesh dimension (scales with mesh size)
  - Use larger of scale-based or base tolerance (clamped to 1e-5 to 0.01 meters)
  - Record slice_thickness_used in warnings/diagnostics so we can confirm it applied
  - Keep previous behavior as baseline fallback if needed

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round55_20260127_223000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round55_20260127_223000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round55_20260127_223000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round55_20260127_223000/KPI_DIFF.md`

## PR Link
[Round55 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - [counts from facts_summary - may be empty if all cases succeeded]
- **Alpha Fail Reasons TopK** (alpha_fail_reasons_topk):
  - [reason]: [count] (empty if no failures occurred)
- **Too Few Points Diagnostics Summary** (too_few_points_diagnostics_summary):
  - [empty if no TOO_FEW_POINTS failures occurred]
  - If present: n_slice_points_raw, n_slice_points_after_dedupe, slice_thickness_used, slice_plane_level (each with min/p50/p95/max/count)
- **Failure Reasons TopK Overall**: [from facts_summary]
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
