# garment_lab

Local laboratory for garment operations.

## Progress (Ops)

1. PROGRESS_LOG.jsonl is the source of truth (append-only).
2. Do NOT edit exports/brief/*_WORK_BRIEF.md by hand (generated).
3. **Roundwrap Only**: Progress events must be recorded via `roundwrap` start/end.
4. **Mandatory Step-ID**: Missing `step_id` results in exit code 2 (no append).
5. If step has no changes, append NOOP event via roundwrap.
6. Main repo reads this log to render STATUS.

## Run End Hook

At run completion, append progress event:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_end_hook.ps1
```

Optional ENV: `GARMENT_STEP_ID`, `GARMENT_DOD_DONE_DELTA`, `GARMENT_DOD_TOTAL`, `GARMENT_STATUS`, `GARMENT_NOTE`.
