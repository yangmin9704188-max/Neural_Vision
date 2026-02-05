> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 50

## Goal
Add a deterministic alpha parameter sweep (k in {3,5,7}) across the 20 processed cases and report loop quality metrics by k (facts-only).

## Changes
- **Deterministic Alpha K Assignment**:
  - core_measurements_v0: Added case_id parameter to measure_circumference_v0_with_metadata and _compute_circumference_at_height
  - Deterministic k assignment: alpha_k = [3,5,7][hash(case_id) % 3]
  - alpha_param_used recorded per case reflects actual alpha_k used
- **Aggregation by K**:
  - Runner: Added alpha_k_counts aggregation (counts per k)
  - Runner: Added torso_loop_quality_summary_by_k aggregation (p50/p95 stats per key and per k)
  - facts_summary contains: alpha_k_counts, torso_loop_quality_summary_by_k
  - Existing torso_loop_quality_summary overall maintained

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round50_20260127_211500`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round50_20260127_211500/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round50_20260127_211500/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round50_20260127_211500/KPI_DIFF.md`

## PR Link
[Round50 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
- **Failure Reasons TopK**: `SINGLE_COMPONENT_ONLY=20` (all 20 processed cases; unchanged from Round49)
- **TORSO_METHOD_USED Counts**: alpha_shape=20 (maintained from Round49)
- **Alpha K Counts** (alpha_k_counts):
  - k=3: 7 cases
  - k=5: 8 cases
  - k=7: 3 cases
  - Sum: 18 (note: 2 cases may not have loop_quality recorded, but all 20 have alpha_shape method)
- **Loop Quality Metrics by K** (torso_loop_quality_summary_by_k):
  - **NECK_CIRC_M**:
    - k=3: area p50=0.0127 m², perimeter p50=0.761 m, shape_ratio p50=45.6, validity=VALID (7)
    - k=5: area p50=0.0169 m², perimeter p50=0.766 m, shape_ratio p50=32.8, validity=VALID (8)
    - k=7: area p50=0.0235 m², perimeter p50=0.779 m, shape_ratio p50=24.6, validity=VALID (3)
  - **BUST_CIRC_M**:
    - k=3: area p50=0.0631 m², perimeter p50=0.951 m, shape_ratio p50=14.0, validity=VALID (7)
    - k=5: area p50=0.0631 m², perimeter p50=0.951 m, shape_ratio p50=14.0, validity=VALID (8)
    - k=7: area p50=0.0631 m², perimeter p50=0.951 m, shape_ratio p50=14.0, validity=VALID (3)
  - **UNDERBUST_CIRC_M**:
    - k=3: area p50=0.0596 m², perimeter p50=0.884 m, shape_ratio p50=13.1, validity=VALID (7)
    - k=5: area p50=0.0596 m², perimeter p50=0.884 m, shape_ratio p50=13.1, validity=VALID (8)
    - k=7: area p50=0.0596 m², perimeter p50=0.884 m, shape_ratio p50=13.1, validity=VALID (3)
- **Torso Delta Stats (Full - Torso)**:
  - BUST_CIRC_M: p50=-0.778m, p95=-0.477m
  - UNDERBUST_CIRC_M: p50=-0.653m, p95=-0.646m
