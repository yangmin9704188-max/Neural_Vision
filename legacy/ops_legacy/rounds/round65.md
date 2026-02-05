> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 65

## Goal
Add exec-fail observability wiring to explain "processed!=skipped" discrepancy with minimal behavior change. Rerun with Round64 manifest (200 enabled cases).

## Changes
- **Exec-Fail Observability** (NO behavior change):
  - Added `log_exec_failure()` function to track cases that reach measurement stage but fail to be counted as processed
  - Created `artifacts/exec_failures.jsonl` for exec-fail case logging
  - Added facts_summary aggregations (always emit, even if empty):
    - `exec_fail_count`: int
    - `exec_fail_stage_topk`: dict (top10)
    - `exec_fail_exception_type_topk`: dict (top10)
    - `exec_fail_case_ids_sample`: dict (exception_type -> first 3 case_ids)
  - Modified `process_case()` to call `log_exec_failure()` when measurement raises exception
  - File: `verification/runners/run_geo_v0_s1_facts.py`

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round65_20260128_105806`
- **manifest**: `verification/manifests/s1_manifest_v0_round64.json` (same as Round64)
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round65_20260128_105806/facts_summary.json`
- **exec_failures.jsonl**: `verification/runs/facts/geo_v0_s1/round65_20260128_105806/artifacts/exec_failures.jsonl`
- **KPI**: `verification/runs/facts/geo_v0_s1/round65_20260128_105806/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round65_20260128_105806/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/237

## Notes
- **Run Statistics**:
  - total_cases=200
  - processed_cases=199
  - skipped_cases=0
  - has_mesh_path_true=200
  - has_mesh_path_null=0

- **Exec-Fail Observability Results**:
  - exec_fail_count=0
  - exec_fail_stage_topk={} (empty)
  - exec_fail_exception_type_topk={} (empty)
  - exec_fail_case_ids_sample={} (empty)
  - **Result**: No exec-fail cases detected at measurement stage

- **Processed vs Skipped Discrepancy**:
  - processed_cases=199, skipped_cases=0, but total_cases=200
  - Discrepancy: 1 case (200 - 199 = 1) is not counted as processed or skipped
  - Exec-fail observability wiring is present and working (exec_fail_count=0)
  - The 1 missing case is NOT an exec-fail at measurement stage
  - Further investigation needed to identify the specific case and stage where it's lost

- **Boundary Recovery Usage**:
  - Same as Round64 (no behavior change)

- **New Fields Presence**:
  - All exec-fail aggregation fields are present in facts_summary.json
  - Fields correctly emit empty values when no exec-fails occur
  - Observability wiring is ready for future exec-fail detection
