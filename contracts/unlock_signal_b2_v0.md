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

## A4) Optional: recommendations (advisory only)

When the generator is run with `--recommend_thresholds`, it may add an optional **recommendations** section. This is **advisory only** and **does not change unlock_candidate**; unlock_candidate is computed solely from user-provided thresholds.

### recommendations (optional, in unlock_signal.json)

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | UTC Z, ISO 8601 (when recommendations were computed) |
| `based_on_metrics` | array of strings | Metric names used (e.g. residual_cm p90 per key, quality_score p90/min) |
| `suggested_thresholds` | object | Candidate values considered |
| `suggested_thresholds.threshold_residual_p90_cm_candidates` | array of numbers | e.g. [0.8, 1.0, 1.2] (cm) |
| `suggested_thresholds.threshold_score_candidates` | array of numbers | e.g. [65, 70, 75] |
| `implied_rates` | object or null | Per-candidate implied pass rates when computable |
| `implied_rates.implied_ok_fraction` | number or null | Fraction above score threshold (only when summary provides it; else null) |
| `implied_rates.notes` | array of strings | Warnings, e.g. FRACTION_NOT_AVAILABLE when cannot compute |
| `combined_rows` | array of objects | Cartesian product: residual_candidate × score_candidate with booleans (all_keys_meet_p90, quality_meets_p90, would_be_candidate_by_p90) |

If summary.json does not provide enough to estimate implied fraction-above-threshold, set `implied_ok_fraction` = null and add a warning (e.g. FRACTION_NOT_AVAILABLE). Do not infer from thin air.

---

## Important

- Do **not** claim "B2 unlocked"; only provide signal + reasons.
- Do **not** fail CI or stop pipelines based on these thresholds; the output is for human decision.
