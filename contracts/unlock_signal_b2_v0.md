# Unlock Signal B2 v0

**Purpose**: Facts-only contract for the "B2 unlock signal" produced from a beta_fit_v0 run. No hard gating: CI and pipelines must NOT fail based on quality thresholds. The output enables humans to decide unlock based on stable, deterministic metrics.

**Schema Version**: `unlock_signal.b2.v0`

---

## A1) Inputs

- **beta_fit_v0 run_dir** containing:
  - `summary.json` (required): beta_fit_v0 summary with quality_score_stats, residual_cm_stats, bucket_counts, dominant_pattern_counts, failures.
  - `residual_report.json` (optional): if present, may be used for richer reasons; not required for unlock_signal generation.

---

## A2) Required fields in unlock_signal.json

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string (const) | `"unlock_signal.b2.v0"` |
| `run_dir` | string | Normalized path to the beta_fit_v0 run directory |
| `created_at` | string | UTC Z, ISO 8601 with seconds (e.g. `2026-02-07T07:31:49Z`) |
| `source` | object | `beta_fit_schema_version` (string), `tool_version` (string) |
| `metrics` | object | See below |
| `rules` | object | Declared thresholds used to compute candidate flag (facts-only) |
| `unlock_candidate` | boolean | true/false; no PASS/FAIL judgment, only signal + reasons |
| `reasons` | array of strings | Facts-only explanations (e.g. "failures_count=0 (<= max_failures=0)") |
| `warnings` | array of strings | Non-fatal issues (missing fields, NaN replaced by null, etc.) |

### metrics (required)

- `quality_score`: `{ p50, p90, min }` (numbers or null)
- `residual_cm`: per key `{ p50, p90, max }` (numbers or null)
- `failures_count`: integer
- `bucket_counts`: `{ OK, LOW }` (integers)
- `dominant_pattern_counts`: object (e.g. TORSO_UPPER, TORSO_MID, TORSO_LOWER)

### rules (required, recorded in output)

- Thresholds used for this run (e.g. `threshold_score`, `threshold_residual_p90_cm`, `max_failures`, `threshold_fraction_above_score`). All thresholds are configurable and must be recorded in the output.

---

## A3) Candidate evaluation (facts-only)

The generator computes `unlock_candidate` by applying the following **example** rules. Thresholds are configurable and must be recorded in `rules` and in the emitted JSON.

- **failures_count** ≤ `max_failures` (e.g. 0).
- **residual_p90_cm** for each key: `|residual_p90_cm[key]|` ≤ `threshold_residual_p90_cm` (e.g. 1.0 cm). Units: cm.
- **quality_score_p90** ≥ `threshold_score` (e.g. 70). Same scale as beta_fit quality_score (0–100).
- **fraction_above_score_threshold** ≥ `threshold_fraction_above_score` (optional; e.g. 0.95). Fraction of prototypes with quality_score ≥ `threshold_score`.

If any rule is not met, `unlock_candidate` is false and the failed rule(s) are listed in `reasons`. No PASS/FAIL judgment is implied; only "unlock_candidate" and explicit reasons.

---

## Output files

- **unlock_signal.json**: Atomic write; deterministic for same input summary.json and thresholds.
- **KPI_UNLOCK.md**: Human-readable, facts-only (tables/bullets); atomic write.

---

## Important

- Do **not** claim "B2 unlocked"; only provide signal + reasons.
- Do **not** fail CI or stop pipelines based on these thresholds; the output is for human decision.
