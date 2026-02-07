# Ops STATUS

## Editing Rule
- Body 섹션은 Cursor만 수정
- Fitting/Garment 섹션은 해당 에이전트만 수정
- Generated 마커 밖은 자동화가 건드리지 않는다

## Manual (ops auto-refresh checks)
- Check scheduler: `Get-ScheduledTaskInfo -TaskName "NeuralVision-Ops-Refresh"`
- Check log tail: `Get-Content exports/logs/ops_refresh.log -Tail 50`
- Check lab roots: open `ops/lab_roots.local.json`

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
*Updated: 2026-02-07 17:46:14*

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
- health: OK (warnings=0)
- brief_path: C:\Users\caino\Desktop\fitting_lab\exports\brief\FITTING_WORK_BRIEF.md
- brief_mtime: 2026-02-07 17:46:14
- brief_head:
  # FITTING Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: fitting
  updated_at: 2026-02-07 17:46:14 +0900
  run_id: N/A
  phase: N/A
  status: OK
  summary: last_step=F01 dod_done=0 | run end hook
  artifacts: N/A
  warnings: 0
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
- health: OK (warnings=0)
- brief_path: C:\Users\caino\Desktop\garment_lab\exports\brief\GARMENT_WORK_BRIEF.md
- brief_mtime: 2026-02-07 17:46:14
- brief_head:
  # GARMENT Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: garment
  updated_at: 2026-02-07 17:46:14 +0900
  run_id: N/A
  phase: N/A
  status: OK
  summary: last_step=G01 dod_done=1 | run end hook
  artifacts: N/A
  warnings: 0
<!-- GENERATED:END:GARMENT -->
