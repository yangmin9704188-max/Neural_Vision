# Measurement Engine Closure Spec (Example)

## Metadata
- feature_id: `body.measurement_engine_v1`
- module: `body`
- owner: `body_main`
- related_step_id: `B40_M1_BUDGET_TELEMETRY_TRACK`
- m_level: `M1`
- unlock_target: `U1`

## Problem Statement
- Provide deterministic body measurement extraction for downstream fitting contracts.
- Close the process so future iterations cannot drift in key naming, units, and evidence handling.

## Input Contract
- Body mesh inputs required by measurement pipeline.
- Unit contract must remain meters (`unit=m`).
- Required key subset for U1 handoff must be emitted without NaN.

## Output Contract
- Emits `body_measurements_subset.json` and `geometry_manifest.json`.
- Emits runtime telemetry (`latency`, `gpu_time`, `vram_peak`, `cache_hit`) for operational tracking.
- Missing values follow freeze policy (single null soft, 2+ null degraded warning).

## Implementation Scope
- Included:
  - deterministic measurement extraction and subset mapping.
  - cache-key policy (`prototype_id,height_quant_2cm,pose_id`).
- Excluded:
  - non-PZ1 pose variants.
  - downstream fitting solver behavior.

## Validation Plan
1. `py tools/validate/validate_u1_body.py --run-dir <BODY_RUN_DIR>`
2. `py tools/smoke/run_u2_smokes.py --only smoke3_degraded`
3. telemetry artifact review in run output.

## DoD (Closure)
1. Implementation evidence exists in run outputs.
2. Validation report exists and linked.
3. Progress log includes `lifecycle_state=CLOSED` with this spec path.

## Evidence Index
- closure_spec_path: `contracts/closure_specs/body/measurement_engine.closure_spec.md`
- validation_report_path: `reports/validation/body/B40_M1_BUDGET_TELEMETRY_TRACK.validation_report.md`
- run_evidence_paths:
  - `exports/runs/.../body_measurements_subset.json`
  - `exports/runs/.../geometry_manifest.json`
