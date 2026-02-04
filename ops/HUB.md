# Ops HUB

## Purpose
- 운영 진입점: 링크/규칙/현재 상태 위치 안내
- STATUS.md에서 모듈별 상태를 확인한다.

## Global Rules (Do/Don't)
- Do: evidence-first, 링크로만 참조, data/**/exports/**는 로컬 전용
- Don't: 모듈 간 파일 직접 수정 금지, 섹션 침범 금지

## Write Boundary (facts-only)
- data/**, exports/**는 로컬 전용, 커밋 금지
- Hub가 외부 lab에 쓸 수 있는 경로는 `exports/brief/**` 뿐 (레거시 [EXPORT_CONTRACT_v0](docs/ops/dashboard_legacy/EXPORT_CONTRACT_v0.md) 인용)

## DoD Claim 규약
- evidence 없으면 claim 금지. 경로 정확 일치 필요.
- 레거시 [DOD_CLAIM_PROTOCOL_v1](docs/ops/dashboard_legacy/DOD_CLAIM_PROTOCOL_v1.md) 참조

## Commands
- `py tools/render_status.py` — STATUS.md BODY 갱신
- docs/ops/dashboard_legacy/ 는 참조용, 실행 비권장

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
