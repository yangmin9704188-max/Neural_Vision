# Ops Hub (진입점)

## SSoT / 계약 / 산출물 경로

| 용도 | 경로 |
|------|------|
| SSoT | ssot/ |
| Contracts | contracts/ |
| Run 산출물 원본 | exports/runs/ |
| 진행 로그 | exports/progress/PROGRESS_LOG.jsonl (여기 누적) |

## 정책
- exports/ 하위: generated-only (수동 편집 금지)
- PROGRESS_LOG.jsonl: append-only
