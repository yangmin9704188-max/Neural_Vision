# B2 Unlock Signal v0 — Final Report

Facts-only. No hard gating; output enables humans to decide unlock.

---

## A) Contract doc path + key excerpts

**Path:** `contracts/unlock_signal_b2_v0.md`

### Required fields in unlock_signal.json

- `schema_version`: `"unlock_signal.b2.v0"`
- `run_dir`: string (normalized)
- `created_at`: UTC Z, ISO 8601 seconds
- `source`: `{ beta_fit_schema_version, tool_version }`
- `metrics`: quality_score (p50, p90, min), residual_cm per key (p50, p90, max), failures_count, bucket_counts, dominant_pattern_counts
- `rules`: declared thresholds used to compute candidate flag
- `unlock_candidate`: true/false
- `reasons`: list of strings (facts-only)
- `warnings`: list of strings

### Candidate evaluation rules (facts-only)

- **failures_count** ≤ max_failures (e.g. 0)
- **residual_p90_cm** per key: |residual_p90_cm[key]| ≤ threshold_residual_p90_cm (e.g. 1.0 cm). Units: cm.
- **quality_score_p90** ≥ threshold_score (e.g. 70)
- **fraction_above_score_threshold** ≥ threshold_fraction_above_score (optional). Thresholds configurable and recorded in output.

---

## B) Tool CLI + example run command

**CLI:**
```bash
python tools/generate_unlock_signal_b2_v0.py \
  --run_dir <beta_fit_v0_run_dir> \
  --out_dir <same_run_dir_or_subdir> \
  --threshold_score 70 \
  --threshold_residual_p90_cm 1.0 \
  --max_failures 0
```

**Example run (Step4 run_dir):**
```bash
python tools/generate_unlock_signal_b2_v0.py \
  --run_dir exports/runs/facts/beta_fit_v0/run_20260207_162505 \
  --out_dir exports/runs/facts/beta_fit_v0/run_20260207_162505 \
  --threshold_score 70 \
  --threshold_residual_p90_cm 1.0 \
  --max_failures 0
```

Optional: `--threshold_fraction_above_score <float>`, `--log-progress` (append B04 event + run render_status), `--created_at <ISO_UTC>` (for determinism tests).

---

## C) unlock_signal.json snippet (first ~25 lines)

```json
{
  "schema_version": "unlock_signal.b2.v0",
  "run_dir": "<RUN_DIR>",
  "created_at": "2026-02-07T07:41:48Z",
  "source": {
    "beta_fit_schema_version": "beta_fit_v0",
    "tool_version": "1.0"
  },
  "metrics": {
    "quality_score": {
      "p50": 79.18,
      "p90": 86.951,
      "min": 66.26
    },
    "residual_cm": {
      "BUST_CIRC_M": {
        "p50": 0.2398,
        "p90": 3.5427999999999997,
        "max": 7.6979
      },
      "WAIST_CIRC_M": {
        "p50": 9.212399999999999,
        "p90": 12.415719999999999,
        "max": 14.3801
      },
      ...
    },
    "failures_count": 0,
    "bucket_counts": { "OK": 378, "LOW": 6 },
    "dominant_pattern_counts": { "TORSO_UPPER": 2, "TORSO_MID": 171, "TORSO_LOWER": 211 }
  },
  "rules": { "threshold_score": 70.0, "threshold_residual_p90_cm": 1.0, "max_failures": 0 },
  "unlock_candidate": false,
  "reasons": [ ... ],
  "warnings": []
}
```

---

## D) Determinism test result (sha256 match)

- **Test:** `tests/test_unlock_signal_b2_determinism.py`
- **Fixture:** `tests/fixtures/beta_fit_summary/summary.json`
- **Method:** Run generator twice with same run_dir, same thresholds, fixed `--created_at 2026-02-07T12:00:00Z`; compare sha256(unlock_signal.json).
- **Result:** sha256 match (both runs produce identical unlock_signal.json).
- **Example sha256** (fixture run, one invocation): `11e27780af2e0c138850aefed56a4195a7d8c05cf44d396e854965796f5ef31b`

---

## E) STATUS generated snippet line (wired)

When run with `--log-progress`, the tool appends a progress event (step_id B04) and runs `tools/render_status.py`, so the BODY "Latest progress" section includes:

```
[B04] 2026-02-07T16:41:52+09:00: B2 unlock signal: candidate=false, quality_p90=86.95, residual_p90_cm={BUST_CIRC_M:3.54...,HIP_CIRC_M:-4.69...,WAIST_CIRC_M:12.42...}, failures=0, run_dir=exports/runs/facts/beta_fit_v0/run_<RUN_ID>
```

---

*Branch `feat/contracts-b2-unlock-signal-v0` merged via PR #11.*
