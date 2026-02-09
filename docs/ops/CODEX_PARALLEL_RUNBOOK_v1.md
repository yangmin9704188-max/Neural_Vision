# CODEX_PARALLEL_RUNBOOK_v1

## 1) Directory Map
- Main worktree: `C:\Users\caino\Desktop\Neural_Vision`
- Body worktree: `C:\Users\caino\Desktop\NV_wt_body`
- Garment worktree: `C:\Users\caino\Desktop\NV_wt_garment`
- Fitting worktree: `C:\Users\caino\Desktop\NV_wt_fitting`

## 2) Touched Paths Rule
- Body agent: only `modules/body/**` (tests under `modules/body/**` if needed).
- Garment agent: only `modules/garment/**`.
- Fitting agent: only `modules/fitting/**`.
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

## 5) Codex Starter Prompts
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
- Allowed touched paths: modules/garment/** only.
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
- Allowed touched paths: modules/fitting/** only.
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
