# Validation Report Template v1

## Metadata
- feature_id: `<module>.<feature_name>`
- related_step_id: `<STEP_ID>`
- module: `body | garment | fitting | common`
- run_id: `<RUN_ID>`
- generated_at_utc: `YYYY-MM-DDTHH:MM:SSZ`

## Validation Inputs
- Input artifacts:
  - `<path>`
- Tool versions / version keys:
  - `<key>: <value>`

## Executed Checks
1. Command: `<command>`
   - Result: `PASS | WARN | FAIL`
   - Evidence: `<path>`
2. Command: `<command>`
   - Result: `PASS | WARN | FAIL`
   - Evidence: `<path>`

## Observed Output Facts
- Required outputs found: `yes/no`
- Hard gate behavior: `<fact-only>`
- Warning/degraded behavior: `<fact-only>`

## Verdict
- validation_state: `VALIDATED | NOT_VALIDATED`
- blocking_issues:
  - `<issue or N/A>`

## Evidence Index
- report_path: `reports/validation/<module>/<STEP_ID>.validation_report.md`
- referenced_run_paths:
  - `<exports/runs/...>`
