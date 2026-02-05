> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 53

## Goal
Eliminate TORSO method tracking_missing cases (wiring-only). Optionally always emit empty topk sections to avoid "missing key" confusion.

## Changes
- **Torso Method Tracking Completeness Fix**:
  - Round53: Ensure that for SINGLE_COMPONENT_ONLY cases, the torso method is always set explicitly
  - Fixed issue where torso_method_used_count showed tracking_missing=4
  - Added fallback: if torso_method_used is still None after all methods, set to "single_component_fallback"
  - Exception handling: For SINGLE_COMPONENT_ONLY cases, ensure method is set even on exception
  - Result: torso_method_used_count.tracking_missing must be 0
- **Always Emit Empty Breakdown Sections**:
  - Round53: Always emit empty dict sections in facts_summary to reduce operator confusion
  - key_exec_fail_breakdown_topk: {} (even when no EXEC_FAIL occurs)
  - key_exception_type_topk: {} (even when no exceptions occur)
  - key_exception_fingerprint_topk: {} (even when no exceptions occur)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round53_20260127_215500`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round53_20260127_215500/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round53_20260127_215500/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round53_20260127_215500/KPI_DIFF.md`

## PR Link
[Round53 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - alpha_shape: 19
  - single_component_fallback: 1
  - tracking_missing: 0 (fixed, was 4 in Round52)
  - Sum: 20 (equals processed_cases)
- **Empty Breakdown Sections** (always emitted):
  - key_exec_fail_breakdown_topk: {} (empty because no EXEC_FAIL occurred)
  - key_exception_type_topk: {} (empty because no exceptions occurred)
  - key_exception_fingerprint_topk: {} (empty because no exceptions occurred)
- **Failure Reasons TopK Overall**: SINGLE_COMPONENT_ONLY=20 (unchanged from Round52)
- **Alpha K Counts**: k=3: 7, k=5: 8, k=7: 5 (sum=20, equals processed_cases)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
