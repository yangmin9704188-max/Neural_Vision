# Closure Spec Template v1

## Metadata
- feature_id: `<module>.<feature_name>`
- module: `body | garment | fitting | common`
- owner: `<agent_or_team>`
- related_step_id: `<STEP_ID>`
- m_level: `M0 | M1 | M2`
- unlock_target: `U1 | U2 | N/A`

## Problem Statement
- What process/feature is being closed.
- Why closure is required now.

## Input Contract
- Required input artifacts.
- Required schema/version keys.
- Pre-checks and hard-gates.

## Output Contract
- Required output artifacts.
- Warning/degraded semantics.
- Determinism requirements.

## Implementation Scope
- Included behavior.
- Explicitly excluded behavior.

## Validation Plan
- Validators/commands used.
- Smoke or integration scenarios.
- Expected evidence paths.

## DoD (Closure)
1. Implementation evidence exists.
2. Validation report exists.
3. Lifecycle state reaches `CLOSED` in progress log.

## Risks / Rollback
- Known risks.
- Rollback path.

## Evidence Index
- closure_spec_path: `contracts/closure_specs/<module>/<STEP_ID>.closure_spec.md`
- validation_report_path: `reports/validation/<module>/<STEP_ID>.validation_report.md`
- run_evidence_paths:
  - `<exports/runs/...>`
