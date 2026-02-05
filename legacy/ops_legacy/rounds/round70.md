> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 70

## Goal
Create deduplicated manifest to resolve duplicate case_id issue identified in Round68-69.

## Context
- Round68 identified manifest contains duplicate case_id: `20_F_3012` appears 2 times
- Round69 added manifest duplicate observability confirming 1 duplicate
- This round creates NEW deduplicated manifest and runs with it

## Changes
- **Manifest Deduplication** (data quality fix):
  - Created new manifest file: `verification/manifests/s1_manifest_v0_round70.json`
  - Input manifest: `verification/manifests/s1_manifest_v0_round64.json` (200 entries, 199 unique case_ids, 1 duplicate)
  - Output manifest: `verification/manifests/s1_manifest_v0_round70.json` (199 entries, 199 unique case_ids, 0 duplicates)
  - **Dedup rule**: Keep first occurrence, drop later duplicates
  - **Removed duplicate**: `20_F_3012` (appeared 2 times, kept first occurrence only)
  - Deduplication script: `tools/deduplicate_manifest.py` (temporary, one-time use)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round70_20260128_213445`
- **manifest**: `verification/manifests/s1_manifest_v0_round70.json` (NEW, deduplicated)
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round70_20260128_213445/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round70_20260128_213445/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round70_20260128_213445/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/243

## Findings (Facts-Only)

### Run Statistics
- total_cases=199 (was 200 in Round69)
- processed_cases=199 (was 199 in Round69)
- skipped_cases=0
- has_mesh_path_true=199
- has_mesh_path_null=0

### Manifest Duplicate Fields (Resolved)
- **manifest_total_entries**: 199 (was 200 in Round69)
- **manifest_unique_case_ids**: 199 (was 199 in Round69)
- **manifest_duplicate_case_id_count**: 0 (was 1 in Round69)
- **manifest_duplicate_case_id_topk**: `{}` (was `{"20_F_3012": 2}` in Round69)
- **manifest_duplicate_case_ids_sample**: `[]` (was `["20_F_3012"]` in Round69)

### Other Observability Fields
- record_expected_total=199
- record_actual_total=199
- record_missing_count=0
- exec_fail_count=0
- processed_sink_count=0
- success_not_processed_count=0

### KPI Diff vs Round69 (Prev)
- **Total cases**: 199 (Δ: -1, expected due to deduplication)
- **HEIGHT_M p50**: 1.7283m (Δ: +0.0000m, stable)
- **HEIGHT_M p95**: 1.7449m (Δ: +0.0000m, stable)
- **BUST_CIRC_M p50**: 1.7273m (Δ: +0.0000m, stable)
- **WAIST_CIRC_M p50**: 1.3086m (Δ: +0.0000m, stable)
- **HIP_CIRC_M p50**: 1.6363m (Δ: +0.0000m, stable)
- **NaN rates**: All top5 keys unchanged (0.00%)
- **Failure reasons**: SINGLE_COMPONENT_ONLY=199 (was 199 in Round69)

## Validation
The deduplication successfully:
- Removed 1 duplicate case_id from manifest (20_F_3012)
- Reduced total_cases from 200 to 199
- Achieved manifest_duplicate_case_id_count=0 (clean state)
- Preserved all measurement statistics (p50/p95 unchanged)
- Maintained processed_cases=199 (all cases now unique and processable)

## Notes
- Manifest is now clean: 199 unique case_ids with zero duplicates
- All observability fields show healthy state (no duplicates, no missing records, no sinks)
- Measurement statistics remain stable after deduplication
- Future rounds should use the deduplicated manifest (round70) as the new baseline
