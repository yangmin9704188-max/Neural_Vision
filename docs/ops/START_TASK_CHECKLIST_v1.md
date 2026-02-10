# Start Task Checklist v1

## Goal
- Start every task with the same sequence.
- Prevent path drift and preserve parallel-module velocity.

## Unified Start Routine (Mandatory)
1. Resolve execution root first.
- Body/Common (`B*`, `C*`): this repo (`Neural_Vision`) only.
- Fitting (`F*`): external lab root from `FITTING_LAB_ROOT` or `ops/lab_roots.local.json`.
- Garment (`G*`): external lab root from `GARMENT_LAB_ROOT` or `ops/lab_roots.local.json`.
2. Lock common references in this order.
- `docs/ops/PIPELINE_EXECUTION_PRINCIPLE_v1.md`
- `docs/ops/PIPELINE_MAP_MASTER_v1.md`
- `contracts/master_plan_v1.json`
3. Pick exactly one step from Hub planner.
- `py tools/agent/next_step.py --module all --top 5 --json`
- Freeze one `step_id` and one `pipeline_stage_id` before coding.
4. Run module-local commands only for the selected step.
- Module-specific smoke/runner commands are allowed.
- They must still satisfy `master_plan` DoD and evidence paths.
5. Close with shared gates.
- Append progress to module-owned `exports/progress/PROGRESS_LOG.jsonl` (append-only).
- Refresh Hub status: `py tools/ops/run_ops_loop.py --mode quick`.
- Before PR: `py tools/ops/run_ops_loop.py --mode full` and `py tools/ci/ci_guard.py`.
6. Conflict rule.
- If module README/runbook conflicts with SSoT/contract, follow SSoT (`contracts/*`, `docs/ops/*`) and update the module runbook.

## 0) New Environment Bootstrap (Required)
1. Open repo and fetch remote refs.
- `git fetch --all --prune`
2. Create or switch to the target branch.
- New branch: `git checkout -b <branch_name> origin/main`
- Existing branch: `git checkout <branch_name>`
3. Sync branch head.
- `git pull --ff-only`
4. Verify location and branch.
- `git rev-parse --abbrev-ref HEAD`
- `git status --short`

## 1) Lock Reference Order (Required)
1. `docs/ops/PIPELINE_EXECUTION_PRINCIPLE_v1.md`
2. `docs/ops/PIPELINE_MAP_MASTER_v1.md`
3. `contracts/master_plan_v1.json`

## 2) Pick Exactly One Step
1. Run:
- `py tools/agent/next_step.py --module all --top 5 --json`
2. Choose one ready step with explicit `pipeline_stage_id`.
3. Freeze this step as current scope (no multi-step expansion).

## 3) Freeze Done Criteria Before Coding
- From selected step in `contracts/master_plan_v1.json`, confirm:
  - `depends_on`
  - `dod`
  - `commands`
  - `closure.validation_report_path`
  - `closure.closure_spec_path`

## 4) Boundary Gate
- Body: in-repo paths only.
- Garment/Fitting: external lab roots only (`GARMENT_LAB_ROOT`, `FITTING_LAB_ROOT`).
- If boundary is unclear, fix topology/path first.

## 5) Implement Minimal Change
- Touch only files required to close the selected step.
- If scope grows, split into a new step and finish current evidence first.

## 6) Evidence Validation
- Run step commands from `master_plan`.
- Run validators/smokes only as required by the step.
- Example: `py tools/smoke/run_u2_smokes.py` (when applicable).

## 7) Progress + Status Update
1. Append progress event with evidence.
- `py tools/ops/append_progress_event.py ...`
2. Quick loop:
- `py tools/ops/run_ops_loop.py --mode quick`
3. Before PR:
- `py tools/ops/run_ops_loop.py --mode full`

## 8) Completion Decision (Both Required)
- Pipeline gap reduced for the selected `pipeline_stage_id`.
- DoD closed by contract-compatible evidence.

## 9) Speed Mode Guardrails
- Local development: keep checks lightweight.
- PR gate enforces strict checks:
  - `tools/ci/ci_guard.py --enforce-stage-path`
  - `tools/ops/run_ops_loop.py --mode full`
