> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 51

## Goal
Fix Round50 regressions in observability/completeness (facts-only), without algorithm tuning.

## Changes
- **Alpha K Aggregation Completeness Fix**:
  - Round51: Ensure every processed case contributes exactly one alpha_k to alpha_k_counts
  - Fixed issue where alpha_k_counts summed to 18 while processed=20
  - Added case-level tracking (alpha_k_recorded_per_case) to prevent duplicate counting
  - For alpha_shape cases: use loop_quality if available, otherwise compute from case_id
  - For tracking_missing cases: compute from case_id (deterministic)
  - Result: alpha_k_counts sum now equals processed_cases (20)
- **Key-Level Failure Reason Aggregation**:
  - Round51: Added key_failure_reasons_topk aggregation for WAIST/HIP NaN regression tracking
  - Keys tracked: WAIST_CIRC_M, WAIST_WIDTH_M, WAIST_DEPTH_M, HIP_CIRC_M, HIP_WIDTH_M
  - Records per-case failure codes when value is NaN
  - Extracts failure reason from metadata warnings or debug_info
  - Aggregates into facts_summary["key_failure_reasons_topk"] with top 5 reasons per key

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round51_20260127_213500`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round51_20260127_213500/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round51_20260127_213500/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round51_20260127_213500/KPI_DIFF.md`

## PR Link
[Round51 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **Alpha K Counts** (alpha_k_counts):
  - k=3: 10 cases
  - k=5: 4 cases
  - k=7: 6 cases
  - Sum: 20 (equals processed_cases, completeness fixed)
- **WAIST/HIP NaN Rates**:
  - WAIST_CIRC_M: nan_rate=1.0 (20/20 NaN)
  - WAIST_WIDTH_M: nan_rate=1.0 (20/20 NaN)
  - WAIST_DEPTH_M: nan_rate=1.0 (20/20 NaN)
  - HIP_CIRC_M: nan_rate=1.0 (20/20 NaN)
  - HIP_WIDTH_M: nan_rate=1.0 (20/20 NaN)
- **Key Failure Reasons TopK** (key_failure_reasons_topk):
  - WAIST_CIRC_M: EXEC_FAIL=20
  - WAIST_WIDTH_M: EXEC_FAIL=20
  - WAIST_DEPTH_M: EXEC_FAIL=20
  - HIP_CIRC_M: EXEC_FAIL=20
  - HIP_WIDTH_M: EXEC_FAIL=20
- **Failure Reasons TopK Overall**: SINGLE_COMPONENT_ONLY=20 (unchanged from Round50)
- **TORSO_METHOD_USED Counts**: alpha_shape=16, tracking_missing=4 (unchanged from Round50)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
