> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 57

## Goal
Reduce ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS by adding a deterministic boundary recovery path (facts-only). No KPI clamping.

## Changes
- **Boundary Recovery Path (Deterministic)**:
  - Round57: When alpha boundary extraction yields n_loops_found=0 or n_boundary_points<3:
    Attempt a recovery before single_component_fallback:
    - Option A: alpha_relax (deterministic)
      - Use alpha_k_eff = min(alpha_k, 3) and retry boundary extraction once
      - Record alpha_k_eff_used in diagnostics
    - Option B: secondary boundary builder (geometry-only)
      - Build a boundary from the 2D points via a simple deterministic method (kNN graph outer boundary)
      - Use more aggressive threshold (75th percentile) for boundary detection
      - Require >=3 boundary points to be considered valid
  - If recovery succeeds, continue with torso perimeter computation
  - If both fail, keep single_component_fallback
- **Tracking + Aggregation**:
  - Round57: Add counters in facts_summary.json:
    - boundary_recovery_used_count: {alpha_relax: n, secondary_builder: n, none: n}
    - boundary_recovery_success_count: {alpha_relax: n, secondary_builder: n}
  - Extend diagnostics summary for failure cases to include post-recovery n_boundary_points if attempted
  - Record boundary_recovery_method and boundary_recovery_success in torso_diagnostics

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round57_20260127_230403`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round57_20260127_230403/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round57_20260127_230403/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round57_20260127_230403/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/226

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - alpha_shape: 20
  - single_component_fallback: 0
  - Sum: 20 (equals processed_cases)
  - Improvement: All 20 cases now use alpha_shape (was 17 in Round56)
- **Alpha Fail Reasons TopK** (alpha_fail_reasons_topk) - stage-specific:
  - {} (empty - no failures occurred)
  - Improvement: ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS reduced from 3 to 0
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: 3, none: 17}
  - boundary_recovery_success_count: {secondary_builder: 3}
  - Explanation: 3 cases used secondary_builder recovery, all succeeded (100% success rate)
  - alpha_relax: 0 (not used - all cases that needed recovery had alpha_k <= 3 already)
- **Too Few Points Diagnostics Summary** (too_few_points_diagnostics_summary) highlights:
  - {} (empty - no TOO_FEW_POINTS failures occurred after recovery)
- **Failure Reasons TopK Overall**: [from facts_summary]
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
