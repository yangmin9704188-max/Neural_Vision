# Feature Closure Protocol v1

## Purpose
- Define a single completion contract for every `master_plan` step.
- Separate lifecycle states into `IMPLEMENTED`, `VALIDATED`, `CLOSED`.
- Force evidence-first completion with explicit artifact paths.

## Scope
- Applies to all modules: `body`, `garment`, `fitting`, `common`.
- Applies to all maturity tracks: `M0`, `M1`, `M2`.

## Lifecycle States
- `IMPLEMENTED`: runnable behavior exists and step output is produced.
  - Minimum evidence: run output path or signal path in progress event evidence.
- `VALIDATED`: validator/smoke/report confirms expected behavior.
  - Minimum evidence: validation report path (`reports/validation/**`) and validator command/result reference.
- `CLOSED`: implementation and validation are frozen as a reusable process contract.
  - Minimum evidence: closure spec path (`contracts/closure_specs/**`) referenced by progress event.

## Required Artifacts Per Step
Every step in `contracts/master_plan_v1.json` MUST include `closure`:

```json
{
  "closure": {
    "feature_id": "<module>.<step_id_lower>",
    "closure_spec_path": "contracts/closure_specs/<module>/<STEP_ID>.closure_spec.md",
    "validation_report_path": "reports/validation/<module>/<STEP_ID>.validation_report.md",
    "lifecycle_states_required": ["IMPLEMENTED", "VALIDATED", "CLOSED"]
  }
}
```

Rules:
- Paths must be repo-relative.
- Absolute paths are forbidden.
- `closure_spec_path` and `validation_report_path` are required even before files are created.
- Completion claim is invalid without both paths.

## Progress Event Contract (Append-only)
Recommended fields for each completion event:

```json
{
  "step_id": "B40_M1_BUDGET_TELEMETRY_TRACK",
  "status": "OK",
  "lifecycle_state": "VALIDATED",
  "closure_spec_ref": "contracts/closure_specs/body/B40_M1_BUDGET_TELEMETRY_TRACK.closure_spec.md",
  "validation_report_ref": "reports/validation/body/B40_M1_BUDGET_TELEMETRY_TRACK.validation_report.md"
}
```

Interpretation:
- `lifecycle_state=IMPLEMENTED`: implementation checkpoint.
- `lifecycle_state=VALIDATED`: validator/smoke/report checkpoint.
- `lifecycle_state=CLOSED`: closure spec finalized and linked.

## Step Completion Rule
A step is considered fully complete only when all are true:
1. `IMPLEMENTED` observed.
2. `VALIDATED` observed with report evidence.
3. `CLOSED` observed with closure spec evidence.

If only 1 is met, status is implementation-only.
If 1 and 2 are met, status is validated but not closed.

## STATUS Rendering Rule
`ops/STATUS.md` generated blocks must show, per module:
- `lifecycle_total_steps`
- `lifecycle_implemented`
- `lifecycle_validated`
- `lifecycle_closed`
- `lifecycle_pending`

## Cross-module Unblock Matrix
- Body produces `body_measurements_subset.json` + `geometry_manifest.json` -> Fitting can start consumer validation.
- Garment produces `garment_proxy_meta.json` + `garment_fit_hint.json` + `geometry_manifest.json` -> Fitting can start garment integration.
- Fitting produces `fitting_facts_summary.json` + `geometry_manifest.json` -> Generation integration can start.
- Each producer step must reach at least `VALIDATED` before consumer marks corresponding integration step as `IMPLEMENTED`.

## Governance
- `tools/agent/plan_lint.py` enforces closure fields in plan.
- `tools/render_work_briefs.py` and `tools/render_status.py` render lifecycle counts from logs.
- Missing closure fields in plan are `FAIL`.
