# B2 Threshold Recommendations — Final Report

Advisory only; recommendations do not change unlock_candidate.

---

## A) Contract diff excerpt (recommendations section)

**Path:** `contracts/unlock_signal_b2_v0.md`

**New section A4) Optional: recommendations (advisory only)**

- When generator is run with `--recommend_thresholds`, it may add optional **recommendations** section.
- **Advisory only; does not change unlock_candidate**; unlock_candidate is computed solely from user-provided thresholds.

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | UTC Z, ISO 8601 |
| `based_on_metrics` | array of strings | Metric names used |
| `suggested_thresholds` | object | threshold_residual_p90_cm_candidates, threshold_score_candidates |
| `implied_rates` | object | implied_ok_fraction (or null), at_threshold_score, notes (e.g. FRACTION_NOT_AVAILABLE) |
| `combined_rows` | array | Cartesian product: residual_candidate × score_candidate with all_keys_meet_p90, quality_meets_p90, would_be_candidate_by_p90 |

If summary does not provide fraction-above-threshold, set implied_ok_fraction = null and add FRACTION_NOT_AVAILABLE.

---

## B) Example CLI command used

```bash
python tools/generate_unlock_signal_b2_v0.py \
  --run_dir <beta_fit_run_dir> \
  --out_dir <out_dir> \
  --threshold_score 70 \
  --threshold_residual_p90_cm 1.0 \
  --max_failures 0 \
  --recommend_thresholds \
  --residual_threshold_candidates "0.8,1.0,1.2" \
  --score_threshold_candidates "65,70,75"
```

Optional: `--created_at <ISO_UTC>`, `--emit_recommendations_only` (skip progress event).

---

## C) unlock_signal.json recommendations snippet

```json
"recommendations": {
  "generated_at": "2026-02-07T12:00:00Z",
  "based_on_metrics": ["residual_cm.p90_per_key", "quality_score.p90", "quality_score.min", "failures_count"],
  "suggested_thresholds": {
    "threshold_residual_p90_cm_candidates": [0.8, 1, 1.2],
    "threshold_score_candidates": [65, 70, 75]
  },
  "residual_candidate_results": [
    { "threshold_residual_p90_cm": 0.8, "meets_p90_per_key": {...}, "all_keys_meet_p90": false },
    { "threshold_residual_p90_cm": 1, "all_keys_meet_p90": true },
    ...
  ],
  "score_candidate_results": [
    { "threshold_score": 65, "quality_meets_p90": true, "quality_meets_min": true },
    ...
  ],
  "combined_rows": [
    { "residual_thr_p90_cm": 0.8, "score_thr_p90": 65, "all_keys_meet_p90": false, "quality_meets_p90": true, "would_be_candidate_by_p90": false, "notes": ["residual_or_quality_threshold_not_met"] },
    { "residual_thr_p90_cm": 1, "score_thr_p90": 70, "all_keys_meet_p90": true, "quality_meets_p90": true, "would_be_candidate_by_p90": true, "notes": [] },
    ...
  ],
  "implied_rates": { "implied_ok_fraction": 0.9, "at_threshold_score": 70, "notes": [] },
  "warnings": []
}
```

---

## D) KPI_UNLOCK.md recommendations table snippet

```markdown
## Recommended thresholds (advisory)
| residual_thr_p90_cm | score_thr_p90 | all_keys_meet_p90 | quality_meets_p90 | would_be_candidate_by_p90 | notes |
|--------------------|--------------|-------------------|-------------------|---------------------------|-------|
| 0.8 | 65 | False | True | False | residual_or_quality_threshold_not_met |
| 0.8 | 70 | False | True | False | residual_or_quality_threshold_not_met |
| 1.0 | 65 | True | True | True | - |
| 1.0 | 70 | True | True | True | - |
| 1.2 | 75 | True | True | True | - |

- implied_ok_fraction: 0.9
- at_threshold_score: 70
```

---

## E) Tests passed + sha256 determinism result

- **test_recommendations_double_run_same_hash**: Run generator twice with `--recommend_thresholds` and fixed `--created_at 2026-02-07T12:00:00Z`; sha256(unlock_signal.json) identical. **Passed.**
- **test_without_recommend_thresholds_no_recommendations_key**: Without `--recommend_thresholds`, output does not contain `recommendations` key. **Passed.**
- **test_double_run_same_output_hash** (existing): Without recommendations, two runs still byte-identical. **Passed.**

**Example sha256** (fixture run with `--recommend_thresholds`, one invocation):

`cef31b4427142c6a532f1febba533b5d41afae4f450718370d2d45588612e0ab`

---

*Branch `feat/b2-threshold-recommendations` merged via PR #14.*
