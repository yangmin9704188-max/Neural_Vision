> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 58

## Goal
Scale coverage from 20 to 50 cases (Tier2 manual backfill) and observe boundary recovery usage at larger sample size (facts-only).

## Changes
- **Manifest Coverage Expansion**:
  - Round58: Created `verification/manifests/s1_manifest_v0_round58.json` with 50 enabled cases
  - Kept existing 20 mesh_path-enabled cases from Round46
  - Added 30 more null cases and assigned to known-good OBJ proxies
  - OBJ assignment: Round-robin distribution across `6th_20M.obj` (10 cases), `6th_30M.obj` (10 cases), `6th_40M.obj` (10 cases)
  - Selected case_ids: First 30 null cases from Round46 manifest
- **BACKFILL_LOG.md Entry**:
  - Round58: Appended manual backfill log entry describing coverage expansion

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round58_20260127_231000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round58_20260127_231000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round58_20260127_231000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round58_20260127_231000/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/227

## Notes
- **Run Statistics**: total_cases=200, processed=50, skipped=150, has_mesh_path_true=50, has_mesh_path_null=150
- **Coverage**: Expanded from 20 to 50 cases using Round58 manifest
- **TORSO_METHOD_USED Counts** (torso_method_used_count):
  - alpha_shape: 50
  - single_component_fallback: 0
  - Sum: 50 (equals processed_cases)
- **Alpha Fail Reasons TopK** (alpha_fail_reasons_topk) - stage-specific:
  - {} (empty - no failures occurred)
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: 4, none: 46}
  - boundary_recovery_success_count: {secondary_builder: 4}
  - Explanation: 4 cases used secondary_builder recovery, all succeeded (100% success rate)
  - alpha_relax: 0 (not used - all cases that needed recovery had alpha_k <= 3 already)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 50 cases have numeric values)
- **Failure Reasons TopK Overall**: [from facts_summary]
