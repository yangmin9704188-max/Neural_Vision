# B2 Unlock Readiness Auto-Generation — Final Report

Facts-only. Never gate; never fail CI on unlock_candidate.

---

## A) End hook file modified

**Path:** `tools/ops/run_end_ops_hook.py`

- Before `render_work_briefs` / `render_status`: calls `_run_b2_unlock_readiness()`.
- Discovers latest beta_fit_v0 run via `find_latest_beta_fit_run(REPO_ROOT)`; if found runs `generate_unlock_signal_b2_v0.py` with `--run_dir`, `--out_dir` (same), `--threshold_score 70`, `--threshold_residual_p90_cm 1.0`, `--max_failures 0`; idempotency: skips `--log-progress` when existing `unlock_signal.json` rules match; if not found appends WARN progress event. All in try/except; exit 0 always.

---

## B) Discovery rule

- **Script:** `tools/ops/find_latest_beta_fit_run.py`
- **Search:** Under `exports/runs/**` for `summary.json` where path contains `beta_fit_v0`. Excludes paths containing `verification`.
- **Latest:** 1) Parse parent dir name as `run_YYYYMMDD_HHMMSS` → datetime, use its timestamp for sorting. 2) If not parseable, use `summary.json` mtime. Sort by newer first (descending), return first run_dir (directory containing `summary.json`).
- **Documented:** Timestamp parsing is used when run_id matches; else mtime fallback.

---

## C) Example latest run_dir found (local; not committed)

When the full Step4 run exists, discovery can return (timestamp-based):

- `exports/runs/facts/beta_fit_v0/run_20260207_162505`

When only a subset run exists or has newer mtime, example:

- `exports/runs/facts/beta_fit_v0/determinism_subset_run2`

(Local absolute path was used only under `exports/`; no repo-tracked files contain absolute paths.)

---

## D) unlock_signal.json presence + snippet

- **Location:** Under the discovered run_dir: `unlock_signal.json` and `KPI_UNLOCK.md` (atomic).
- **Snippet (key fields):**

```json
{
  "schema_version": "unlock_signal.b2.v0",
  "run_dir": "<RUN_DIR>",
  "metrics": {
    "quality_score": { "p50": 82.51, "p90": 86.40, "min": 69.75 },
    "residual_cm": {
      "BUST_CIRC_M": { "p50": 0.72, "p90": 2.08, "max": 2.15 },
      "WAIST_CIRC_M": { "p50": 7.05, "p90": 12.98, "max": 13.38 },
      "HIP_CIRC_M": { "p50": -8.78, "p90": -5.32, "max": -5.04 }
    },
    "failures_count": 0
  },
  "rules": { "threshold_score": 70.0, "threshold_residual_p90_cm": 1.0, "max_failures": 0 },
  "unlock_candidate": false,
  "reasons": [ "failures_count=0 (<= max_failures=0)", "residual_p90_cm[BUST_CIRC_M]=... (|...| > 1.0)", ... ]
}
```

---

## E) STATUS generated snippet line

After running the end hook, the BODY "Latest progress" section includes a B04 line, e.g.:

```
[B04] 2026-02-07T17:01:49+09:00: B2 unlock signal: candidate=false, quality_p90=86.40, residual_p90_cm={BUST_CIRC_M:2.08...,HIP_CIRC_M:-5.32...,WAIST_CIRC_M:12.98...}, failures=0, run_dir=exports\runs\facts\beta_fit_v0\determinism_subset_run2
```

---

## Manual verification (done)

- End hook run locally: `py tools/ops/run_end_ops_hook.py`
- `unlock_signal.json` and `KPI_UNLOCK.md` generated under the discovered beta_fit_v0 run_dir.
- `ops/STATUS.md` GENERATED section shows B04 unlock readiness line(s).
- No absolute local paths written into repo-tracked files (outputs under `exports/` only).

---

*Branch `feat/ops-b2-unlock-readiness-auto` merged via PR #13.*
