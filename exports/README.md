# Exports

## Purpose
- generated-only. 산출물(런 결과, progress, briefs, dashboards) 저장.

## Do / Don't
- Do: 도구/스크립트가 생성.
- Don't: 수동 편집 금지.

## Key files
- runs/: geo_v0_s1, curated_v0 등 런 산출물
- progress/PROGRESS_LOG.jsonl: append-only 진행 로그

## How to run
- N/A (생성 전용)

## Outputs
- exports/runs/<lane>/<run_id>/
- exports/progress/PROGRESS_LOG.jsonl

## References
- ops/HUB.md
