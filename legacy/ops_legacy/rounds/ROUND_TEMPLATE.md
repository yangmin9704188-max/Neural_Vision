# Round XX

## Goal
[라운드 목표를 간단히 기술]

## Changes
[주요 변경사항을 나열]

## Artifacts
- **run_dir**: `verification/runs/facts/<lane>/roundXX_YYYYMMDD_HHMMSS`
- **report**: `reports/validation/<report_name>.md`

## PR Link
[PR 링크 또는 PR 번호]

## Progress Events (dashboard)

```jsonl
{"lab":"hub","module":"body","step_id":"B01","dod_done_delta":1,"dod_total":3,"evidence_paths":["docs/ops/rounds/roundXX.md"],"note":"<one-line summary>"}
```

> 위 블록에 이번 라운드의 dashboard progress event를 기록한다.
> postprocess_round 실행 시 자동으로 PROGRESS_LOG.jsonl에 ingest 된다.
> 이벤트가 없으면 블록을 비우거나 섹션 자체를 생략해도 무방하다.

## Notes
[추가 메모, 이슈, 후속 작업 등]
