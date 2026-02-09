# CODEX_PARALLEL_RUNBOOK_v1

## 1) Directory Map
- Main worktree: `C:\Users\caino\Desktop\Neural_Vision`
- Body worktree: `C:\Users\caino\Desktop\Neural_Vision` (main/hub)
- Garment lab repo: configured by `GARMENT_LAB_ROOT` (example: `C:\Users\caino\Desktop\garment_lab`)
- Fitting lab repo: configured by `FITTING_LAB_ROOT` (example: `C:\Users\caino\Desktop\fitting_lab`)

## 2) Touched Paths Rule
- Body agent: only `modules/body/**` (tests under `modules/body/**` if needed).
- Garment agent: only `GARMENT_LAB_ROOT/**` in garment repo.
- Fitting agent: only `FITTING_LAB_ROOT/**` in fitting repo.
- Deprecated in this repo: `modules/garment/**`, `modules/fitting/**` (legacy mirror; do not edit).
- Common lane only: any change to `contracts/**`, `tools/validate/**`, `tools/ops/**`, `ops/HUB.md`.

## 3) Standard Operating Loop (Per Worktree)
### Start of Task
- `py tools/agent/next_step.py --module <module> --top 5`

### End of Task (Before PR)
- `py tools/ops/doctor.py`
- `py tools/ci/ci_guard.py`
- `py tools/smoke/run_u2_smokes.py`
- `py tools/ops/run_ops_loop.py --mode full`
- Option A hygiene:
- `git restore ops/STATUS.md`
- delete `.tmp_pr_body.txt` if it exists
- `git status --porcelain` must be empty

## 4) PR Workflow (Per Module Branch)
- Create feature branch off `wt/<module>` when needed.
- Commit only within allowed touched paths.
- Push branch and open PR.
- Merge only when CI is green and user approves merge timing.

## 5) Round/Level Contract (R10+)
- Plan contract now supports `rounds[]`, step `round_id`, step `m_level` (`M0|M1|M2`), and optional `consumes[].min_level`.
- Backward compatibility defaults:
- missing step `m_level` => treated as `M0`
- missing dependency `min_level` => treated as `M0`
- Progress events may include `m_level` (`append_progress_event.py --m-level`), and `next_step.py` computes per-step `done_levels`.
- `next_step --json` now exposes level-aware blockers when dependency level is below required minimum.

## 6) Codex Starter Prompts
### Body
```text
ROLE
- You are the Body module agent.
- Worktree: C:\Users\caino\Desktop\NV_wt_body

TOUCH RULE
- Allowed touched paths: modules/body/** only (tests under modules/body/** if needed).
- Do not touch contracts/**, tools/validate/**, tools/ops/**, ops/HUB.md (common lane only).

END COMMANDS (required)
- py tools/ops/doctor.py
- py tools/ci/ci_guard.py
- py tools/smoke/run_u2_smokes.py
- py tools/ops/run_ops_loop.py --mode full

HYGIENE
- git restore ops/STATUS.md
- delete .tmp_pr_body.txt if present
- git status --porcelain must be empty
```

### Garment
```text
ROLE
- You are the Garment module agent.
- Worktree: C:\Users\caino\Desktop\NV_wt_garment

TOUCH RULE
- Allowed touched paths: GARMENT_LAB_ROOT/** only (garment external repo).
- Do not touch contracts/**, tools/validate/**, tools/ops/**, ops/HUB.md (common lane only).

END COMMANDS (required)
- py tools/ops/doctor.py
- py tools/ci/ci_guard.py
- py tools/smoke/run_u2_smokes.py
- py tools/ops/run_ops_loop.py --mode full

HYGIENE
- git restore ops/STATUS.md
- delete .tmp_pr_body.txt if present
- git status --porcelain must be empty
```

### Fitting
```text
ROLE
- You are the Fitting module agent.
- Worktree: C:\Users\caino\Desktop\NV_wt_fitting

TOUCH RULE
- Allowed touched paths: FITTING_LAB_ROOT/** only (fitting external repo).
- Do not touch contracts/**, tools/validate/**, tools/ops/**, ops/HUB.md (common lane only).

END COMMANDS (required)
- py tools/ops/doctor.py
- py tools/ci/ci_guard.py
- py tools/smoke/run_u2_smokes.py
- py tools/ops/run_ops_loop.py --mode full

HYGIENE
- git restore ops/STATUS.md
- delete .tmp_pr_body.txt if present
- git status --porcelain must be empty
```
