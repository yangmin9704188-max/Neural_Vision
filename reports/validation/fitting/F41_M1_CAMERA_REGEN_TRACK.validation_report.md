# F41 Validation Report

## Metadata
- feature_id: `fitting.f41_m1_camera_regen_track`
- related_step_id: `F41_M1_CAMERA_REGEN_TRACK`
- module: `fitting`
- run_id: `20260209_122811_fitting_m1`
- generated_at_utc: `2026-02-09T12:55:00Z`

## Validation Inputs
- Input artifacts:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
  - `ops/signals/m1/fitting/LATEST.json`
- Tool versions / version keys:
  - `camera_preset_id: fixed_camera_preset_v1`
  - `retry_regen_policy: regen_loop.v1`

## Executed Checks
1. Command: `py tools/validate/validate_u1_fitting.py --run-dir C:\Users\caino\Desktop\Neural_Vision\data\shared_m1\fitting\20260209_122811_fitting_m1`
   - Result: `PASS`
   - Evidence: `data/shared_m1/fitting/20260209_122811_fitting_m1/fitting_facts_summary.json`
2. Command: `F40_F41_CONTRACT_CHECK` (fixed camera + retry/regen constraints + audit fields)
   - Result: `PASS`
   - Evidence: `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`, `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`

## Observed Output Facts
- Required outputs found: `yes`
- Hard gate behavior: `not triggered`
- Warning/degraded behavior: `none`
- F41 DoD mapping:
  - fixed_camera_preset_v1 consistent: `yes`
  - retry loop constraints/audit fields preserved: `yes` (`max_retry=2`, `iter_max_per_attempt=100`, attempt telemetry recorded)

## Verdict
- validation_state: `VALIDATED`
- blocking_issues:
  - `N/A`

## Evidence Index
- report_path: `reports/validation/fitting/F41_M1_CAMERA_REGEN_TRACK.validation_report.md`
- closure_spec_path: `contracts/closure_specs/fitting/F41_M1_CAMERA_REGEN_TRACK.closure_spec.md`
- referenced_run_paths:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
  - `ops/signals/m1/fitting/LATEST.json`
