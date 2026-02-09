# Lab Topology Policy (2026-02-10)

## Scope
- This policy is the operational override for multi-agent parallel work.
- It applies to Body Hub (main repo) and external Garment/Fitting lab repos.

## Canonical Topology
- Body Hub: this repo (`Neural_Vision`), writable for body/common/ops only.
- Fitting Lab: external sibling repo, resolved by `FITTING_LAB_ROOT`.
- Garment Lab: external sibling repo, resolved by `GARMENT_LAB_ROOT`.

## Deprecated Paths
- `modules/fitting/**` and `modules/garment/**` inside this repo are deprecated legacy mirrors.
- Do not implement, patch, or run module workflows from those in-repo paths.

## Source/Write Contract
- Hub -> Lab write is allowed only for `<lab_root>/exports/brief/**`.
- Progress logs are append-only and owned by each module repo:
  - Body: `exports/progress/PROGRESS_LOG.jsonl`
  - Fitting: `<FITTING_LAB_ROOT>/exports/progress/PROGRESS_LOG.jsonl`
  - Garment: `<GARMENT_LAB_ROOT>/exports/progress/PROGRESS_LOG.jsonl`

## Agent Assignment
- Body agent: `B*` and `C*` steps only.
- Fitting agent: `F*` steps only (in fitting lab repo).
- Garment agent: `G*` steps only (in garment lab repo).

## Required Environment
- Configure one of:
  - env vars: `FITTING_LAB_ROOT`, `GARMENT_LAB_ROOT`
  - local file: `ops/lab_roots.local.json`
- Example values: `../fitting_lab`, `../garment_lab`

## Guardrails
- `py tools/ci/ci_guard.py` blocks edits under in-repo legacy mirror paths.
- `py tools/ops/doctor.py` warns when lab roots point to in-repo mirrors.
- `py tools/agent/next_step.py` reads progress from configured external lab roots.
