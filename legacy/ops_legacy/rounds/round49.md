> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 49

## Goal
Keep alpha_shape method (currently 20/20) and add facts-only loop quality metrics to facts_summary.json to quantify torso extraction behavior.

## Changes
- **Loop Quality Metrics Addition**:
  - core_measurements_v0: Added `_compute_loop_quality_metrics` function to compute loop quality metrics for alpha_shape method
  - Metrics computed: torso_loop_area_m2, torso_loop_perimeter_m, torso_loop_shape_ratio (perimeter^2/area), alpha_param_used (k=5), loop_validity code
  - Metrics recorded in torso_diagnostics["torso_loop_quality"] when alpha_shape method succeeds
- **Runner Aggregation**:
  - Round49: Collect loop quality metrics from torso_loop_quality in torso_info
  - Aggregate into facts_summary["torso_loop_quality_summary"] with p50/p95 summaries and validity counts per key
  - Keep TORSO_METHOD_USED tracking (must remain present)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round49_20260127_210500`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round49_20260127_210500/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round49_20260127_210500/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round49_20260127_210500/KPI_DIFF.md`

## PR Link
[Round49 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage**: Maintained at 20 cases using Round46 manifest
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
- **Failure Reasons TopK**: `SINGLE_COMPONENT_ONLY=20` (all 20 processed cases; unchanged from Round48)
- **TORSO_METHOD_USED Counts**:
  - alpha_shape: 20 (all 20 cases used alpha-shape method; maintained from Round48)
  - cluster_trim: 0
  - single_component_fallback: 0
  - Sum: 20 (equals processed_cases, tracking complete)
- **TORSO_METHOD_USED by Key**: NECK_CIRC_M: alpha_shape=20
- **Loop Quality Metrics Summary** (torso_loop_quality_summary):
  - **NECK_CIRC_M**:
    - torso_loop_area_m2: p50=0.0169 m², p95=0.0327 m²
    - torso_loop_perimeter_m: p50=0.766 m, p95=0.818 m
    - torso_loop_shape_ratio: p50=32.8, p95=36.7
    - alpha_param_used: 5 (all cases)
    - loop_validity: VALID (all 20 cases)
  - **BUST_CIRC_M**:
    - torso_loop_area_m2: p50=0.0631 m², p95=0.0660 m²
    - torso_loop_perimeter_m: p50=0.951 m, p95=0.960 m
    - torso_loop_shape_ratio: p50=14.0, p95=14.3
    - alpha_param_used: 5 (all cases)
    - loop_validity: VALID (all 20 cases)
  - **UNDERBUST_CIRC_M**:
    - torso_loop_area_m2: p50=0.0596 m², p95=0.0621 m²
    - torso_loop_perimeter_m: p50=0.884 m, p95=0.902 m
    - torso_loop_shape_ratio: p50=13.1, p95=13.1
    - alpha_param_used: 5 (all cases)
    - loop_validity: VALID (all 20 cases)
- **Torso Delta Stats (Full - Torso)**:
  - BUST_CIRC_M: p50=-0.778m, p95=-0.477m
  - UNDERBUST_CIRC_M: p50=-0.653m, p95=-0.646m
- **Torso Diagnostics Summary**: Present with `n_intersection_points_summary`, `n_segments_summary`, `n_components_summary` for NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M
