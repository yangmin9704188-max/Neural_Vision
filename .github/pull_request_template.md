## Summary
<!-- Describe the changes in 2-3 sentences -->

## Checklist

### Pre-merge Verification
- [ ] `py tools/ops/doctor.py` (FAIL=0)
- [ ] `py tools/smoke/run_u2_smokes.py` (FAIL=0)
- [ ] `py tools/agent/next_step.py --module all --top 5`
- [ ] `py tools/ops/run_ops_loop.py --mode quick` (or `--mode full`)
- [ ] `py tools/ci/ci_guard.py` (FAIL=0, local pre-check)

### Boundary Compliance
- [ ] No commits to `exports/**` or `data/**` (local-only paths)
- [ ] No modifications to root loose copies (use canonical paths in `contracts/` or `docs/`)
- [ ] PROGRESS_LOG changes are append-only (no deletions/edits)
- [ ] STATUS.md changes (if any) are via render tools, not manual edits

### Documentation
- [ ] Touched paths listed below
- [ ] Related issues/PRs referenced (if any)

## Touched Paths
<!-- List the main files/directories modified -->
```
- path/to/modified/file.py
- path/to/another/file.md
```

## Test Plan
<!-- Describe how changes were verified -->
- [ ] Local testing performed
- [ ] Validators/smokes passed
- [ ] CI checks green

## Additional Notes
<!-- Any extra context, decisions, or follow-up items -->
