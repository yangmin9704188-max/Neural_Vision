# Pipeline

## Purpose
- 데이터 파이프라인: ingest, 정제, 변환.

## Do / Don't
- Do: ingest/ 하위 스크립트 사용.
- Don't: measurements/runners 로직 혼입 금지.

## Key files
- ingest/build_curated_v0.py: curated_v0 생성
- ingest/: 정제, 매핑, 컬럼 관찰 스크립트

## How to run
- ingest/README.md 참조

## Outputs
- data/derived/curated_v0/<RUN_ID>/

## References
- [ingest/README.md](ingest/README.md), contracts/
