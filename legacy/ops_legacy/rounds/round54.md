> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 54

## Goal
Explain (facts-only) why 1 case used single_component_fallback instead of alpha_shape in Round53, by adding alpha failure reason codes and aggregations.

## Changes
- **Alpha Failure Reason Coding**:
  - Round54: When alpha_shape path fails and we fall back, assign a reason code:
    - ALPHA_FAIL:EMPTY_LOOP (perimeter computation failed)
    - ALPHA_FAIL:TOO_FEW_POINTS (boundary extraction failed or len < 3)
    - ALPHA_FAIL:EXCEPTION (exception during alpha_shape computation)
  - Record per-case alpha_fail_reason when fallback happens
  - Store in torso_diagnostics["alpha_fail_reason"] and warnings
- **Aggregation into facts_summary.json**:
  - Round54: Add alpha_fail_reasons_topk: {<reason>: count}
  - Ensure counts match single_component_fallback count
  - Always emit empty dict to avoid missing key confusion

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round54_20260127_222510`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round54_20260127_222510/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round54_20260127_222510/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round54_20260127_222510/KPI_DIFF.md`

## PR Link
[Round54 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - alpha_shape: 19
  - single_component_fallback: 1
  - Sum: 20 (equals processed_cases)
- **Alpha Fail Reasons TopK** (alpha_fail_reasons_topk):
  - ALPHA_FAIL:TOO_FEW_POINTS: 1 (matches single_component_fallback count)
  - Explanation: 1 case used single_component_fallback because alpha_shape boundary extraction failed (too few points)
- **Failure Reasons TopK Overall**: SINGLE_COMPONENT_ONLY=20
- **Alpha K Counts**: k=3: [count], k=5: [count], k=7: [count] (sum=20, equals processed_cases)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
