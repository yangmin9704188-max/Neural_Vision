# F40 Closure Spec

## Metadata
- feature_id: `fitting.f40_m1_fit_signal_track`
- module: `fitting`
- owner: `fitting_main`
- related_step_id: `F40_M1_FIT_SIGNAL_TRACK`
- m_level: `M1`
- unlock_target: `U1`

## Problem Statement
- Close F40 by freezing fit_signal explainability and provenance key surface for M1 fitting handoff.

## Input Contract
- `ops/signals/m1/body/LATEST.json`
- `ops/signals/m1/garment/LATEST.json`
- latest run directory resolved from fitting M1 signal.

## Output Contract
- `fit_signal.json` includes explainability fields (`weights`, `score_components`, `score_total`, `decision_trace`).
- `provenance.json` includes `solver`, `camera`, `cache`, `version_keys`.
- `geometry_manifest.json` and `fitting_facts_summary.json` remain U1-valid.

## Implementation Scope
- Included:
  - fit signal explainability mapping in `modules/fitting/tools/run_m1_e2e.py`
  - provenance key set alignment in `modules/fitting/tools/run_m1_e2e.py`
  - schema extension in `modules/fitting/labs/specs/fit_signal.schema.json`
- Excluded:
  - M2 sensor scoring and regen policy hardening (`F50/F51`).

## Validation Plan
1. `py tools/validate/validate_u1_fitting.py --run-dir <RUN_DIR>`
2. `py modules/fitting/tools/validate_fit_signal.py --fit-signal <RUN_DIR>/fit_signal.json --repo-root modules/fitting`
3. field assertions for explainability/provenance keys.

## DoD (Closure)
1. Implementation evidence exists.
2. Validation report exists.
3. Progress log contains `IMPLEMENTED`, `VALIDATED`, `CLOSED` for this step.

## Risks / Rollback
- Risk: downstream consumers may expect legacy fit_signal without explainability keys.
- Rollback: revert `modules/fitting/tools/run_m1_e2e.py` and `modules/fitting/labs/specs/fit_signal.schema.json` to previous commit.

## Evidence Index
- closure_spec_path: `contracts/closure_specs/fitting/F40_M1_FIT_SIGNAL_TRACK.closure_spec.md`
- validation_report_path: `reports/validation/fitting/F40_M1_FIT_SIGNAL_TRACK.validation_report.md`
- run_evidence_paths:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
