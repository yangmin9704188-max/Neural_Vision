# Ops STATUS

## Editing Rule

- **GENERATED 블록 내부** (`<!-- GENERATED:BEGIN:... -->` ~ `<!-- GENERATED:END:... -->`): 자동 생성 영역, 수동 편집 금지.
- **GENERATED 블록 외부**: 사람이 편집 가능.
- 렌더러(`render_work_briefs` → `render_status`)가 갱신하는 범위는 GENERATED 블록 내부만.

## Manual (ops auto-refresh checks)
- Check scheduler: `Get-ScheduledTaskInfo -TaskName "NeuralVision-Ops-Refresh"`
- Check log tail: `Get-Content exports/logs/ops_refresh.log -Tail 50`
- Check lab roots: open `ops/lab_roots.local.json`

## BLOCKERS (generated)
<!-- GENERATED:BEGIN:BLOCKERS -->
- BLOCKERS Top 5:
  - STEP_ID_BACKFILLED: 7
  - SCHEMA_VIOLATION_BACKFILLED: 6
  - RUN_MANIFEST_ROOT_MISSING: 2
  - EVIDENCE_ONLY_SAMPLES: 1
  - STEP_ID_MISSING: 1
<!-- GENERATED:END:BLOCKERS -->

## M1 Signals (generated)
<!-- GENERATED:BEGIN:M1_SIGNALS -->
- body: run_id=20260209_074047_body_m1; run_dir_rel=../NV_shared_data/shared_m1/body/20260209_074047_body_m1; created_at_utc=2026-02-09T07:41:00Z
- garment: run_id=20260209_123816_garment_m1; run_dir_rel=../NV_shared_data/shared_m1/garment/20260209_123816_garment_m1; created_at_utc=2026-02-09T12:38:17Z
- fitting: run_id=20260209_122811_fitting_m1; run_dir_rel=data/shared_m1/fitting/20260209_122811_fitting_m1; created_at_utc=2026-02-09T12:28:11Z
<!-- GENERATED:END:M1_SIGNALS -->
---

## Body
### Now Unlock
- 
### Next Unlock
- Step2 started: centroid generator v0 skeleton (deterministic seed+ordering, atomic outputs).
### Latest run
- lane:
- run_id:
### Health
- green / yellow / red
### Next 3
- 
- 
- 
### Blockers
- 
### Evidence paths
- curated: data/derived/curated_v0/<RUN_ID>/
- geo: exports/runs/geo_v0_s1/<run_id>/
- contracts: contracts/ (reference only)

### Dashboard (generated-only)
<!-- GENERATED:BEGIN:BODY -->
*Updated: 2026-02-10 02:50:19*

- health: OK (warnings=0)
- lifecycle_total_steps: 9
- lifecycle_implemented: 9
- lifecycle_validated: 0
- lifecycle_closed: 0
- lifecycle_pending: 0
- next_validate: B01, B02, B10_M1_PUBLISH, B20_M2_PLACEHOLDER, B30_M0_DOC_ALIGN

### Curated ingest
- run_dir: data/derived/curated_v0/_smoke/round10_3_20260204_232023
- curated_v0.parquet: 451 rows, 48 cols
  - path: data/derived/curated_v0/_smoke/round10_3_20260204_232023/curated_v0.parquet (80,091 bytes)
- RUN_LOG: N/A

### Geo runner facts
- facts_summary: exports/runs/_smoke/round_atomic_fix/geo_v0_s1/facts_summary.json
  - total=200 processed=5 skipped=195
  - duplicates=1, missing=0, sink=0

### Latest progress
- [B40_M1_BUDGET_TELEMETRY_TRACK] 2026-02-09T21:26:24+09:00: Body M1 telemetry/budget track implemented: latency,gpu_time,vram_peak,cache_hit + violation policy output
- [B50_M2_QUALITY_GATE_TRACK] 2026-02-09T21:42:04+09:00: Body M2 quality gate implemented: deterministic blocked/degraded/promotable exposure policy
- [B51_M2_VERSIONING_TRACK] 2026-02-09T21:42:04+09:00: Body M2 versioning/invalidation hardened: null-free version keys and validated invalidation semantics

<!-- GENERATED:END:BODY -->

---

## Fitting
### Now Unlock
- 
### Next Unlock
- 
### Latest run
- lane:
- run_id:
### Health
- green / yellow / red
### Next 3
- 
- 
- 
### Blockers
- 
### Evidence paths
- fitting runs: exports/runs/fitting_v0/<run_id>/ (placeholder)

### Dashboard (generated-only)
<!-- GENERATED:BEGIN:FITTING -->
- health: WARN (warnings=1)
- health_summary: [RUN_MANIFEST_ROOT_MISSING] round_end_fail | expected=exports/progress/PROGRESS_LOG.jsonl
- lifecycle_total_steps: 11
- lifecycle_implemented: 4
- lifecycle_validated: 0
- lifecycle_closed: 0
- lifecycle_pending: 7
- next_validate: F01, F02, F03, F04
- status_policy_version: status_source_policy.v1
- status_source_selected: work_brief_progress_log
- status_source_updated_at_utc: 2026-02-09T17:50:11Z
- status_source_value: WARN
- status_signal_policy: status_sources_only(work_brief_progress_log,smoke_status_summary); signal=readiness_only(m1_latest_signal)
- status_vs_signal_recency: status_newer
- status_sla_version: status_refresh_sla.v1
- status_sla_max_age_min: 240
- status_source_age_min: 0
- status_sla_state: OK
- signal_source: m1_latest_signal
- signal_created_at_utc: 2026-02-09T12:28:11Z
- signal_run_id: 20260209_122811_fitting_m1
- signal_run_dir_rel: data/shared_m1/fitting/20260209_122811_fitting_m1
- evidence_snapshot: total=26; run_evidence=15, manifest=3, sample=0, other=8
- brief_path: C:\Users\caino\Desktop\fitting_lab\exports\brief\FITTING_WORK_BRIEF.md
- brief_mtime_local: 2026-02-10 02:50:11
- brief_mtime_utc: 2026-02-09T17:50:11Z
- run_level_evidence_primary: N/A
- fitting_facts_summary_path: N/A
- smoke2_garment_input_path_used: N/A
- smoke2_early_exit: N/A
- smoke2_early_exit_reason: N/A
- smoke2_hard_gate_artifact_only_ok: false
- smoke2_warning_classification: N/A
- smoke2_out_dir: N/A
- smoke2_proxy_asset_present: N/A
- smoke_summary_path: N/A
- smoke_summary_updated_at_utc: N/A
- smoke_summary_overall: N/A
- warnings:
  - [RUN_MANIFEST_ROOT_MISSING] round_end_fail | expected=exports/progress/PROGRESS_LOG.jsonl
<!-- GENERATED:END:FITTING -->

---

## Garment
### Now Unlock
- 
### Next Unlock
- 
### Latest run
- lane:
- run_id:
### Health
- green / yellow / red
### Next 3
- 
- 
- 
### Blockers
- 
### Evidence paths
- garment runs: exports/runs/garment_v0/<run_id>/ (placeholder)

### Dashboard (generated-only)
<!-- GENERATED:BEGIN:GARMENT -->
- health: WARN (warnings=1)
- health_summary: [GARMENT_ASSET_MISSING_CLASS_WARN] observed | path=N/A
- lifecycle_total_steps: 9
- lifecycle_implemented: 3
- lifecycle_validated: 0
- lifecycle_closed: 0
- lifecycle_pending: 6
- next_validate: G01, G02, G10_M1_PUBLISH
- status_policy_version: status_source_policy.v1
- status_source_selected: work_brief_progress_log
- status_source_updated_at_utc: 2026-02-09T17:50:11Z
- status_source_value: OK
- status_signal_policy: status_sources_only(work_brief_progress_log,smoke_status_summary); signal=readiness_only(m1_latest_signal)
- status_vs_signal_recency: status_newer
- status_sla_version: status_refresh_sla.v1
- status_sla_max_age_min: 240
- status_source_age_min: 0
- status_sla_state: OK
- signal_source: m1_latest_signal
- signal_created_at_utc: 2026-02-09T12:38:17Z
- signal_run_id: 20260209_123816_garment_m1
- signal_run_dir_rel: ../NV_shared_data/shared_m1/garment/20260209_123816_garment_m1
- evidence_snapshot: total=14; run_evidence=9, manifest=2, sample=0, other=3
- brief_path: C:\Users\caino\Desktop\garment_lab\exports\brief\GARMENT_WORK_BRIEF.md
- brief_mtime_local: 2026-02-10 02:50:11
- brief_mtime_utc: 2026-02-09T17:50:11Z
- run_level_evidence_primary: C:\Users\caino\Desktop\garment_lab\runs\smoke\smoke2\20260210_024342\fitting_facts_summary.json
- fitting_facts_summary_path: C:\Users\caino\Desktop\garment_lab\runs\smoke\smoke2\20260210_024342\fitting_facts_summary.json
- smoke2_garment_input_path_used: unknown
- smoke2_early_exit: True
- smoke2_early_exit_reason: garment_hard_gate_violation: invalid_face_flag
- smoke2_hard_gate_artifact_only_ok: true
- smoke2_warning_classification: GARMENT_ASSET_MISSING:non_blocker
- smoke2_out_dir: C:\Users\caino\Desktop\garment_lab\runs\smoke\smoke2\20260210_024342
- smoke2_proxy_asset_present: False
- smoke_summary_path: C:\Users\caino\Desktop\garment_lab\exports\brief\SMOKE_STATUS_SUMMARY.json
- smoke_summary_updated_at_utc: 2026-02-09T17:50:11Z
- smoke_summary_overall: PASS
- warnings:
  - [GARMENT_ASSET_MISSING_CLASS_WARN] observed | path=N/A
<!-- GENERATED:END:GARMENT -->
