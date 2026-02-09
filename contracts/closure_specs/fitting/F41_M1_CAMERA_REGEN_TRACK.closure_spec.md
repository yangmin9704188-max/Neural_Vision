# F41 Closure Spec

## Metadata
- feature_id: `fitting.f41_m1_camera_regen_track`
- module: `fitting`
- owner: `fitting_main`
- related_step_id: `F41_M1_CAMERA_REGEN_TRACK`
- m_level: `M1`
- unlock_target: `U1`

## Problem Statement
- Close F41 by freezing camera preset invariance and retry/regen telemetry contract for fitting M1.

## Input Contract
- F40-aligned fitting output contract.
- latest fitting M1 signal and run outputs.

## Output Contract
- `fixed_camera_preset_v1` is applied consistently in run artifacts and fitting signal.
- retry/regen telemetry is persisted with `max_retry=2`, `iter_max_per_attempt=100`, and attempt audit fields.

## Implementation Scope
- Included:
  - camera preset constants and propagation in `modules/fitting/tools/run_m1_e2e.py`
  - retry/regen telemetry serialization in fit_signal/provenance/signal outputs
- Excluded:
  - M2 regeneration policy changes (`F51_M2_REGEN_POLICY_TRACK`).

## Validation Plan
1. `py tools/validate/validate_u1_fitting.py --run-dir <RUN_DIR>`
2. contract field assertions on `fit_signal.json`, `provenance.json`, `ops/signals/m1/fitting/LATEST.json`.

## DoD (Closure)
1. Implementation evidence exists.
2. Validation report exists.
3. Progress log contains `IMPLEMENTED`, `VALIDATED`, `CLOSED` for this step.

## Risks / Rollback
- Risk: strict camera/telemetry fields may require downstream parser updates.
- Rollback: revert camera/regen additions in `modules/fitting/tools/run_m1_e2e.py`.

## Evidence Index
- closure_spec_path: `contracts/closure_specs/fitting/F41_M1_CAMERA_REGEN_TRACK.closure_spec.md`
- validation_report_path: `reports/validation/fitting/F41_M1_CAMERA_REGEN_TRACK.validation_report.md`
- run_evidence_paths:
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/fit_signal.json`
  - `data/shared_m1/fitting/20260209_122811_fitting_m1/provenance.json`
  - `ops/signals/m1/fitting/LATEST.json`
