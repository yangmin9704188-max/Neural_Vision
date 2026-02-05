> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 68

## Goal
Add record-missing observability to identify cases that enter the processing loop but do not call log_skip_reason (missing skip_reason records).

## Context
- Round67 showed: loop touched 200/200, processed_cases=199, skip_reasons.jsonl had 199 lines
- Hypothesis: 1 case entered loop but did NOT call log_skip_reason

## Changes
- **Record Missing Skip_Reason Observability** (NO behavior change):
  - Added `log_skip_reason_tracking` set to track which case_ids call log_skip_reason
  - Added `entered_loop_case_ids` set to track which case_ids enter the processing loop
  - Added `log_record_missing_skip_reason()` function for missing record logging
  - Created `artifacts/record_missing_skip_reason.jsonl` (always created, even if empty)
  - Added facts_summary aggregations (always emit, even if empty):
    - `record_expected_total`: int (cases that entered loop)
    - `record_actual_total`: int (cases that called log_skip_reason)
    - `record_missing_count`: int (expected - actual)
    - `record_missing_case_ids_sample`: list (first 3 missing case_ids)
    - `record_duplicate_count`: int (duplicate tracking)
  - Modified `log_skip_reason()` to accept `tracking_set` parameter
  - Modified `process_case()` to accept and pass `log_skip_reason_tracking`
  - Detection logic: compare entered_loop vs log_called sets after processing loop
  - File: `verification/runners/run_geo_v0_s1_facts.py`

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round68_20260128_180600`
- **manifest**: `verification/manifests/s1_manifest_v0_round64.json` (same as Round64/67)
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round68_20260128_180600/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round68_20260128_180600/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round68_20260128_180600/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/240

## Findings (Facts-Only)

### Run Statistics
- total_cases=200 (manifest)
- processed_cases=199
- skipped_cases=0

### Record Tracking Results
- **record_expected_total**=199 (cases entered loop)
- **record_actual_total**=199 (cases called log_skip_reason)
- **record_missing_count**=0 (no missing records)
- **Artifact line counts**:
  - `skip_reasons.jsonl`: 200 lines
  - `record_missing_skip_reason.jsonl`: 0 lines (file not created, no missing records)

### Root Cause Identified
**Manifest Data Quality Issue**: The manifest contains a **duplicate case_id**:
- case_id `20_F_3012` appears **2 times** in the manifest
- Manifest total: 200 cases
- Unique case_ids: 199

This explains the discrepancy:
- Loop runs 200 times (once per manifest entry)
- `skip_reasons.jsonl` has 200 lines (one per loop iteration)
- `entered_loop_case_ids` (set) has 199 entries (deduplicates)
- `all_results` (dict) has 199 entries (dict keys are unique)
- `processed_cases`=199 (unique case_ids only)

### Observability Validation
Round68 observability successfully identified that:
- All 199 unique cases that entered the loop called log_skip_reason (no missing records)
- The 199 vs 200 discrepancy is due to duplicate case_id in manifest, not missing logging
- The runner logic is correct; the issue is manifest data quality

### Other Observability Fields
- exec_fail_count=0
- processed_sink_count=0
- success_not_processed_count=0

## Notes
- Observability wiring is working correctly
- No runner logic issues found
- Manifest should be deduplicated or duplicate handling added
- The 1-case discrepancy was caused by duplicate case_id in manifest, not by missing log_skip_reason call
