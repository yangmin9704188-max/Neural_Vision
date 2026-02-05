> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 69

## Goal
Add manifest duplicate observability to detect and quantify duplicate case_ids in the manifest, exposing them in facts_summary.json.

## Context
- Round68 identified that manifest contains duplicate case_id: `20_F_3012` appears 2 times
- Need observability to detect manifest data quality issues

## Changes
- **Manifest Duplicate Observability** (NO behavior change):
  - Collect manifest case_id list after loading manifest
  - Count duplicates using Counter
  - Add facts_summary fields (always emit, even if no duplicates):
    - `manifest_total_entries`: int (total cases in manifest)
    - `manifest_unique_case_ids`: int (unique case_ids)
    - `manifest_duplicate_case_id_count`: int (number of duplicate case_ids)
    - `manifest_duplicate_case_id_topk`: dict (case_id -> count for count>=2, top10)
    - `manifest_duplicate_case_ids_sample`: list (first 3 duplicate case_ids)
  - Add console logging for duplicate detection
  - File: `verification/runners/run_geo_v0_s1_facts.py`

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round69_20260128_210824`
- **manifest**: `verification/manifests/s1_manifest_v0_round64.json` (same as Round64/67/68)
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round69_20260128_210824/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round69_20260128_210824/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round69_20260128_210824/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/242

## Findings (Facts-Only)

### Run Statistics
- total_cases=200
- processed_cases=199
- skipped_cases=0
- has_mesh_path_true=200
- has_mesh_path_null=0

### Manifest Duplicate Fields (New)
- **manifest_total_entries**: 200 (total cases in manifest)
- **manifest_unique_case_ids**: 199 (unique case_ids)
- **manifest_duplicate_case_id_count**: 1 (number of duplicate case_ids)
- **manifest_duplicate_case_id_topk**: `{"20_F_3012": 2}` (case_id with count>=2)
- **manifest_duplicate_case_ids_sample**: `["20_F_3012"]` (first 3 duplicates)

### Validation
The observability correctly identified:
- 1 duplicate case_id in the manifest
- `20_F_3012` appears 2 times
- This matches Round68's findings

### Other Observability Fields
- record_expected_total=199
- record_actual_total=199
- record_missing_count=0
- exec_fail_count=0
- processed_sink_count=0
- success_not_processed_count=0

## Notes
- Observability wiring is working correctly
- Manifest duplicate detection now available in facts_summary
- The duplicate case_id (`20_F_3012`) is consistently detected across rounds
- This provides data quality visibility for manifest validation
