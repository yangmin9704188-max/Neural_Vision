# Ops HUB

## Purpose
- 운영 진입점: 링크/규칙/현재 상태 위치 안내
- STATUS.md에서 모듈별 상태를 확인한다.

## Global Rules (Do/Don't)
- Do: evidence-first, 링크로만 참조, data/**/exports/**는 로컬 전용
- Don't: 모듈 간 파일 직접 수정 금지, 섹션 침범 금지

## Module Shortcuts
- [Body Status](./STATUS.md#body)
- [Fitting Status](./STATUS.md#fitting)
- [Garment Status](./STATUS.md#garment)

## Evidence Surfaces (read-only)
- Body:
  - curated: data/derived/curated_v0/<RUN_ID>/
  - geo runs: exports/runs/geo_v0_s1/<run_id>/
- Fitting: exports/runs/fitting_v0/<run_id>/ (placeholder)
- Garment: exports/runs/garment_v0/<run_id>/ (placeholder)
