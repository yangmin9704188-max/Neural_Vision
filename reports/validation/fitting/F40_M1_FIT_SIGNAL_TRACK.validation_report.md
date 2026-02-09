# F40 Validation Report

## Metadata
- feature_id: `fitting.f40_m1_fit_signal_track`
- related_step_id: `F40_M1_FIT_SIGNAL_TRACK`
- module: `fitting`
- run_id: `20260209_122811_fitting_m1`
- generated_at_utc: `2026-02-09T12:55:00Z`

## Validation Inputs
- Input artifacts:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/geometry_manifest.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fitting_facts_summary.json`
- Tool versions / version keys:
  - `geometry_impl_version: run_m1_e2e.v2`
  - `snapshot_version: m1`
  - `semantic_version: 0.1.0`

## Executed Checks
1. Command: `py tools/validate/validate_u1_fitting.py --run-dir C:\Users\caino\Desktop\Neural_Vision\data\shared_m1\fitting\20260209_122811_fitting_m1`
   - Result: `PASS`
   - Evidence: `data/shared_m1/fitting/20260209_122811_fitting_m1/fitting_facts_summary.json`
2. Command: `py modules/fitting/tools/validate_fit_signal.py --fit-signal data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json --repo-root modules/fitting`
   - Result: `PASS`
   - Evidence: `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
3. Command: `F40_F41_CONTRACT_CHECK` (camera/provenance/explainability field assertions)
   - Result: `PASS`
   - Evidence: `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`

## Observed Output Facts
- Required outputs found: `yes`
- Hard gate behavior: `none observed in latest run`
- Warning/degraded behavior: `none`
- F40 DoD mapping:
  - fit_signal explainability fields mapped: `yes`
  - provenance has solver/camera/cache/version keys: `yes`

## Verdict
- validation_state: `VALIDATED`
- blocking_issues:
  - `N/A`

## Evidence Index
- report_path: `reports/validation/fitting/F40_M1_FIT_SIGNAL_TRACK.validation_report.md`
- closure_spec_path: `contracts/closure_specs/fitting/F40_M1_FIT_SIGNAL_TRACK.closure_spec.md`
- referenced_run_paths:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
