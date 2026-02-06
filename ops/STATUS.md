# Ops STATUS

## Editing Rule
- Body 섹션은 Cursor만 수정
- Fitting/Garment 섹션은 해당 에이전트만 수정
- Generated 마커 밖은 자동화가 건드리지 않는다

---

## Body
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
- curated: data/derived/curated_v0/<RUN_ID>/
- geo: exports/runs/geo_v0_s1/<run_id>/
- contracts: contracts/ (reference only)

### Dashboard (generated-only)
<!-- GENERATED:BEGIN:BODY -->
*Updated: 2026-02-05 00:51:01*

- health: OK (warnings=0)

### Curated ingest
- run_dir: data/derived/curated_v0/_smoke/round10_3_20260204_232023
- curated_v0.parquet: 451 rows, 48 cols
  - path: data/derived/curated_v0/_smoke/round10_3_20260204_232023/curated_v0.parquet (80,091 bytes)
- RUN_LOG: N/A

### Geo runner facts
- facts_summary: exports/runs/_smoke/round6_6_final/geo_v0_s1/facts_summary.json
  - total=200 processed=200 skipped=0
  - duplicates=0, missing=0, sink=0

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
- brief_mtime: 2026-02-05 00:51:01
- brief_head:
  # FITTING Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: fitting
  updated_at: 2026-02-05 00:51:01 +0900
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
- brief_mtime: 2026-02-05 00:51:01
- brief_head:
  # GARMENT Work Brief
  
  <!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->
  
  module: garment
  updated_at: 2026-02-05 00:51:01 +0900
  run_id: N/A
  phase: N/A
  status: OK
  summary: last_step=G01 dod_done=0 | run end hook
  artifacts: N/A
  warnings: 0
<!-- GENERATED:END:GARMENT -->
