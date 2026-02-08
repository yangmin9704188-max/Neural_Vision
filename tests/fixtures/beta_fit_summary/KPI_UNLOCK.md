# B2 Unlock Signal (facts-only)

- schema_version: unlock_signal.b2.v0
- run_dir: C:\Users\caino\Desktop\Neural_Vision\tests\fixtures\beta_fit_summary
- created_at: 2026-02-07T12:00:00Z
- unlock_candidate: True

## Rules used
- threshold_score: 70.0
- threshold_residual_p90_cm: 1.0
- max_failures: 0

## Metrics
- quality_score: p50, p90, min
  - p50: 85.00
  - p90: 88.00
  - min: 72.00
- residual_cm (p50, p90, max) per key:
  - BUST_CIRC_M: {'p50': '0.2000', 'p90': '0.8000', 'max': '1.2000'}
  - WAIST_CIRC_M: {'p50': '0.3000', 'p90': '0.9000', 'max': '1.3000'}
  - HIP_CIRC_M: {'p50': '-0.4000', 'p90': '-0.7000', 'max': '0.1000'}
- failures_count: 0
- bucket_counts: {'OK': 9, 'LOW': 1}

## Reasons
- failures_count=0 (<= max_failures=0)
- residual_p90_cm[BUST_CIRC_M]=0.8000 (|0.8000| <= 1.0)
- residual_p90_cm[WAIST_CIRC_M]=0.9000 (|0.9000| <= 1.0)
- residual_p90_cm[HIP_CIRC_M]=-0.7000 (|0.7000| <= 1.0)
- quality_p90=88.00 (>= 70.0)

## Recommended thresholds (advisory)
| residual_thr_p90_cm | score_thr_p90 | all_keys_meet_p90 | quality_meets_p90 | would_be_candidate_by_p90 | notes |
|--------------------|--------------|-------------------|-------------------|---------------------------|-------|
| 0.8 | 65 | False | True | False | residual_or_quality_threshold_not_met |
| 0.8 | 70 | False | True | False | residual_or_quality_threshold_not_met |
| 0.8 | 75 | False | True | False | residual_or_quality_threshold_not_met |
| 1.0 | 65 | True | True | True | - |
| 1.0 | 70 | True | True | True | - |
| 1.0 | 75 | True | True | True | - |
| 1.2 | 65 | True | True | True | - |
| 1.2 | 70 | True | True | True | - |
| 1.2 | 75 | True | True | True | - |

- implied_ok_fraction: 0.9
- at_threshold_score: 70