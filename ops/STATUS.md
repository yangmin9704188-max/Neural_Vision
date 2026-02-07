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
*Updated: 2026-02-07 02:15:53*

- health: OK (warnings=0)

### Curated ingest
- run_dir: data/derived/curated_v0/_smoke/round10_3_20260204_232023
- curated_v0.parquet: 451 rows, 48 cols
  - path: data/derived/curated_v0/_smoke/round10_3_20260204_232023/curated_v0.parquet (80,091 bytes)
- RUN_LOG: N/A

### Geo runner facts
- facts_summary: exports/runs/_smoke/round_manifest_fix/geo_v0_s1/facts_summary.json
  - total=200 processed=5 skipped=195
  - duplicates=1, missing=0, sink=0

### Latest progress
- [B01] 2026-02-07T02:05:40+09:00: Phase0 Step1: geometry_manifest.v1 schema+validator+audit; smoke runners emit manifest for body/fitting/garment; audit --check_files exit 0
- [B01] 2026-02-07T02:07:07+09:00: CORRECTION: Phase0 Step1 manifest v1 VERIFIED only for body. Fitting/Garment NOT VERIFIED (no smoke run_dir / no manifest).
- [B01] 2026-02-07T02:15:47+09:00: Phase0 Step1: geometry_manifest.v1 VERIFIED for body + external labs (fitting/garment) via audit --check_files exit 0 | body: exports/runs/_smoke/round_manifest_fix/geo_v0_s1 | fitting: C:/Users/caino/Desktop/fitting_lab/exports/runs/_smoke/20260206_171040/fitting_smoke_v1 | garment: C:/Users/caino/Desktop/garment_lab/exports/runs/_smoke/20260206_171420/garment_smoke_v1

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
- health_summary: [LAB_ROOT_MISSING] FITTING_LAB_ROOT not set | path=N/A
- brief_path: N/A
- brief_mtime: N/A
- warnings:
  - [LAB_ROOT_MISSING] FITTING_LAB_ROOT not set | path=N/A
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
- health_summary: [LAB_ROOT_MISSING] GARMENT_LAB_ROOT not set | path=N/A
- brief_path: N/A
- brief_mtime: N/A
- warnings:
  - [LAB_ROOT_MISSING] GARMENT_LAB_ROOT not set | path=N/A
<!-- GENERATED:END:GARMENT -->
