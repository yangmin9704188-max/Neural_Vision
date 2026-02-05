> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 59

## Goal
Add cohort-level observability comparing loop quality metrics between cases that used boundary_recovery (secondary_builder) vs none. No algorithm changes.

## Changes
- **Recovery Cohort Aggregation**:
  - Round59: Aggregate loop quality metrics into two cohorts:
    - cohort=recovery_used (secondary_builder)
    - cohort=none
  - For each key (NECK/BUST/UNDERBUST) and per cohort, compute:
    - p50/p95 of torso_loop_area_m2, torso_loop_perimeter_m, torso_loop_shape_ratio
    - loop_validity_counts
    - counts
  - Write to facts_summary.json under:
    - boundary_recovery_cohort_summary: {<key>: {recovery_used: {...}, none: {...}}}

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round59_20260127_232000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round59_20260127_232000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round59_20260127_232000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round59_20260127_232000/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/228

## Notes
- **Run Statistics**: total_cases=200, processed=50, skipped=150, has_mesh_path_true=50, has_mesh_path_null=150
- **Coverage**: Maintained at 50 cases using Round58 manifest
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: n, none: n}
  - boundary_recovery_success_count: {secondary_builder: n}
- **Boundary Recovery Cohort Summary** (boundary_recovery_cohort_summary):
  - For each key (NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M):
    - recovery_used cohort: {torso_loop_area_m2: {p50, p95, count}, torso_loop_perimeter_m: {p50, p95, count}, torso_loop_shape_ratio: {p50, p95, count}, loop_validity_counts: {...}, count: n}
    - none cohort: {torso_loop_area_m2: {p50, p95, count}, torso_loop_perimeter_m: {p50, p95, count}, torso_loop_shape_ratio: {p50, p95, count}, loop_validity_counts: {...}, count: n}
  - Highlights (numbers only):
    - NECK_CIRC_M:
      - recovery_used: count=3, area_m2 p50=0.0287, perimeter_m p50=0.774, shape_ratio p50=20.87, validity=VALID:3
      - none: count=47, area_m2 p50=0.0184, perimeter_m p50=0.766, shape_ratio p50=20.87, validity=VALID:47
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: 3, none: 47}
  - boundary_recovery_success_count: {secondary_builder: 3}
- **TORSO_METHOD_USED Counts**: [from facts_summary]
- **Alpha Fail Reasons TopK**: [from facts_summary]
- **Torso Keys NaN Rate**: [from facts_summary]
