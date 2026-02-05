> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 62

## Goal
Surface "enabled-but-skipped" aggregates into facts_summary.json. Wiring-only, no behavior change.

## Changes
- **Enabled-but-skipped Aggregation**:
  - Round62: Added aggregation of skip reasons for enabled cases (has_mesh_path==true AND reason != "success"):
    - enabled_skip_reasons_topk: count of skip reasons for enabled-but-skipped cases (top 10)
    - enabled_skip_stage_topk: count of stages where enabled cases were skipped (top 10)
    - enabled_skip_reason_sample: first 3 case_ids per reason (for debugging)
  - Always emit empty dicts when no enabled-but-skipped cases exist (avoids "missing key" confusion)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round62_20260128_082547`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round62_20260128_082547/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round62_20260128_082547/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round62_20260128_082547/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/231

## Notes
- **Run Statistics**: total_cases=200, processed=50, skipped=150, has_mesh_path_true=100, has_mesh_path_null=100
- **Coverage**: Using Round60 manifest (100 enabled cases)
- **Enabled-but-skipped Aggregation**:
  - enabled_skip_reasons_topk: {"file_not_found": 50}
  - enabled_skip_stage_topk: {"precheck": 50}
  - enabled_skip_reason_sample: {"file_not_found": ["21_F_6996", "20_F_0882", "20_F_0494"]}
  - **Observation**: All 50 enabled-but-skipped cases fail at precheck stage due to file_not_found. This confirms that the mesh files referenced in the manifest do not exist on disk.
