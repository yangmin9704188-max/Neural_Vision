> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 61

## Goal
Explain (facts-only) why processed=50 when manifest has 100 enabled cases, by adding runner selection/cap observability. Do not change behavior yet.

## Changes
- **Runner Selection/Cap Observability**:
  - Round61: Added tracking of runner selection behavior:
    - requested_enabled_cases: count of manifest cases with mesh_path not null
    - effective_processed_cap: the cap actually applied (if none, record null)
    - selection_rule: one-line string describing selection logic
    - selected_case_id_sample: first3 and last3 of selected list
    - total_selected: total number of cases selected for processing
  - Emit this under facts_summary.json as runner_selection_summary

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round61_20260127_235000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round61_20260127_235000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round61_20260127_235000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round61_20260127_235000/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/230

## Notes
- **Run Statistics**: total_cases=200, processed=50, skipped=150, has_mesh_path_true=100, has_mesh_path_null=100
- **Coverage**: Using Round60 manifest (100 enabled cases)
- **Runner Selection Summary** (runner_selection_summary):
  - requested_enabled_cases: 100 (cases with mesh_path not null in manifest)
  - effective_processed_cap: null (no cap applied)
  - selection_rule: "process all cases in manifest order"
  - selected_case_id_sample: {first3: [...], last3: [...]}
  - total_selected: 200 (all cases in manifest)
  - **Observation**: All 200 cases are selected for processing, but only 50 are successfully processed. The difference (100 enabled - 50 processed = 50) suggests that 50 cases with mesh_path are being skipped due to other reasons (e.g., load failures, measurement failures).
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: n, none: n}
  - boundary_recovery_success_count: {secondary_builder: n}
- **Torso Keys NaN Rate**: [from facts_summary]
