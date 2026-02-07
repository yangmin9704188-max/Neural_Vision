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
  - STEP_ID_MISSING: 3
  - STEP_ID_BACKFILLED: 1
  - EVIDENCE_ONLY_SAMPLES: 1
<!-- GENERATED:END:BLOCKERS -->

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
*Updated: 2026-02-08 00:06:58*

- health: OK (warnings=0)

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
- [B03] 2026-02-07T16:31:49+09:00: Step4 beta_fit_v0 full k=384: run_dir=exports/runs/facts/beta_fit_v0/run_20260207_162505 summary sha256=bd76b0f0095d7dc7898a9484a9ccb65c743350ee6fbf11ff14e5d3e4ab964221 quality p50=79.18 p90=86.95 min=66.26 failures=0
- [B04] 2026-02-07T16:41:52+09:00: B2 unlock signal: candidate=false, quality_p90=86.95, residual_p90_cm={BUST_CIRC_M:3.5427999999999997,HIP_CIRC_M:-4.68869,WAIST_CIRC_M:12.415719999999999}, failures=0, run_dir=exports\runs\facts\beta_fit_v0\run_20260207_162505
- [B04] 2026-02-07T17:01:49+09:00: B2 unlock signal: candidate=false, quality_p90=86.40, residual_p90_cm={BUST_CIRC_M:2.0820999999999996,HIP_CIRC_M:-5.31998,WAIST_CIRC_M:12.982859999999999}, failures=0, run_dir=exports\runs\facts\beta_fit_v0\determinism_subset_run2

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
- health_summary: [STEP_ID_MISSING] observed | path=N/A
- brief_path: C:\Users\caino\Desktop\fitting_lab\exports\brief\FITTING_WORK_BRIEF.md
- brief_mtime: 2026-02-08 00:06:57
- observed_paths:
  - exports/runs/_smoke/20260206_164438/fitting_smoke_v1/geometry_manifest.json
  - exports/runs/_smoke/20260206_170827/fitting_smoke_v1/geometry_manifest.json
  - exports/runs/_smoke/20260206_171040/fitting_smoke_v1/geometry_manifest.json
- brief_head:
  # FITTING Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: fitting
  updated_at: 2026-02-08 00:06:57 +0900
  run_id: N/A
  phase: N/A
  status: WARN
  summary: last_step=F_BACKFILL dod_done=1 | Backfill: previous step-id missing event corrected; original run_end_ops_hook UN
  artifacts: N/A
  warnings: STEP_ID_MISSING
- warnings:
  - [STEP_ID_MISSING] observed | path=N/A
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
- health: WARN (warnings=2)
- health_summary: [STEP_ID_MISSING] observed | path=N/A; [STEP_ID_MISSING] observed | path=N/A
- brief_path: C:\Users\caino\Desktop\garment_lab\exports\brief\GARMENT_WORK_BRIEF.md
- brief_mtime: 2026-02-08 00:06:57
- observed_paths:
  - exports/runs/_smoke/20260206_171153/garment_smoke_v1/geometry_manifest.json
  - exports/runs/_smoke/20260206_171153/geometry_manifest.json
  - exports/runs/_smoke/20260206_171420/garment_proxy_meta.json
- brief_head:
  # GARMENT Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: garment
  updated_at: 2026-02-08 00:06:57 +0900
  run_id: N/A
  phase: N/A
  status: WARN
  summary: last_step=G11 dod_done=2 | M0: garment_proxy_meta verified
  artifacts: N/A
  warnings: STEP_ID_MISSING,STEP_ID_MISSING
- warnings:
  - [STEP_ID_MISSING] observed | path=N/A
  - [STEP_ID_MISSING] observed | path=N/A
<!-- GENERATED:END:GARMENT -->
