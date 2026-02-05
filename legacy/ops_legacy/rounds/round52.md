> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 52

## Goal
Break down EXEC_FAIL for WAIST/HIP keys into actionable facts (sub-codes + exception type/fingerprint), without attempting to "fix" the measurements yet.

## Changes
- **EXEC_FAIL Taxonomy + Exception Fingerprinting**:
  - Round52: Added exception classification into sub-codes for WAIST/HIP keys
  - Sub-codes: EXEC_FAIL:SLICE_EMPTY, EXEC_FAIL:TOO_FEW_POINTS, EXEC_FAIL:NUMERIC_ERROR, EXEC_FAIL:UNHANDLED_EXCEPTION
  - Record exception_type (e.__class__.__name__)
  - Record exception_fingerprint: stable short hash (MD5, first 8 chars) over (exception_type + message[:200])
  - Store per-case metadata: exec_fail_subcode, exception_type, exception_fingerprint
- **Aggregations in facts_summary**:
  - Round52: Added key_exec_fail_breakdown_topk (per key, sub-code counts, top 5)
  - Round52: Added key_exception_type_topk (per key, top 5)
  - Round52: Added key_exception_fingerprint_topk (per key, top 5)
  - Round52: Updated key_failure_reasons_topk to handle EXEC_FAIL:SUBCODE format

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round52_20260127_214500`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round52_20260127_214500/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round52_20260127_214500/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round52_20260127_214500/KPI_DIFF.md`

## PR Link
[Round52 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **WAIST/HIP NaN Rates**:
  - WAIST_CIRC_M: nan_rate=0.0 (0/20 NaN, all cases succeeded)
  - WAIST_WIDTH_M: nan_rate=0.0 (0/20 NaN, all cases succeeded)
  - WAIST_DEPTH_M: nan_rate=0.0 (0/20 NaN, all cases succeeded)
  - HIP_CIRC_M: nan_rate=0.0 (0/20 NaN, all cases succeeded)
  - HIP_WIDTH_M: nan_rate=0.0 (0/20 NaN, all cases succeeded)
- **EXEC_FAIL Breakdown**: No EXEC_FAIL occurred in this run (all WAIST/HIP keys succeeded)
  - key_exec_fail_breakdown_topk: Not present (no EXEC_FAIL cases)
  - key_exception_type_topk: Not present (no exceptions)
  - key_exception_fingerprint_topk: Not present (no exceptions)
- **Key Failure Reasons TopK**: Not present (no NaN cases for tracked keys)
- **Failure Reasons TopK Overall**: SINGLE_COMPONENT_ONLY=20 (unchanged from Round51)
- **Alpha K Counts**: k=3: 8, k=5: 4, k=7: 8 (sum=20, equals processed_cases)
- **TORSO_METHOD_USED Counts**: alpha_shape=16, tracking_missing=4 (unchanged from Round51)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
