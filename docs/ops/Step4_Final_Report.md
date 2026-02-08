# Step4 beta_fit_v0 Full Batch — Final Report

Facts-only. Outputs under `exports/` are local-only (not committed).

---

## A) Full run command + out_dir

**Command:**
```bash
python tools/fit_smplx_beta_v0.py \
  --centroids_json exports/runs/_tools/centroids/20260207_125407/centroids_v0.json \
  --out_dir exports/runs/facts/beta_fit_v0/run_20260207_162505 \
  --k 384 \
  --seed 42 \
  --max_iter 200 \
  --pose_id PZ1 \
  --keys BUST_CIRC_M,WAIST_CIRC_M,HIP_CIRC_M
```

**out_dir:** `exports/runs/facts/beta_fit_v0/run_20260207_162505`

---

## B) summary.json key stats

| Metric | Value |
|--------|--------|
| **quality_score** p50 | 79.18 |
| **quality_score** p90 | 86.95 |
| **quality_score** min | 66.26 |
| **residual_cm** BUST p50 | 0.24 |
| **residual_cm** BUST p90 | 3.54 |
| **residual_cm** BUST max | 7.70 |
| **residual_cm** WAIST p50 | 9.21 |
| **residual_cm** WAIST p90 | 12.42 |
| **residual_cm** WAIST max | 14.38 |
| **residual_cm** HIP p50 | -9.36 |
| **residual_cm** HIP p90 | -4.69 |
| **residual_cm** HIP max | 1.99 |
| **failures** count | 0 |
| bucket OK | 378 |
| bucket LOW | 6 |

---

## C) Top-10 worst prototypes

| prototype_id | quality_score | BUST_cm | WAIST_cm | HIP_cm | dominant_residual_key |
|--------------|---------------|---------|----------|--------|------------------------|
| p0072 | 66.26 | 5.94 | 10.83 | -16.97 | TORSO_LOWER |
| p0107 | 66.66 | 3.04 | 13.59 | -16.71 | TORSO_LOWER |
| p0088 | 68.50 | 7.70 | 7.92 | -15.88 | TORSO_LOWER |
| p0302 | 69.46 | 2.74 | 12.48 | -15.32 | TORSO_LOWER |
| p0192 | 69.53 | 2.77 | 12.41 | -15.29 | TORSO_LOWER |
| p0008 | 69.75 | 2.15 | 12.94 | -15.16 | TORSO_LOWER |
| p0128 | 70.04 | 5.16 | 9.73 | -15.07 | TORSO_LOWER |
| p0014 | 70.35 | 3.05 | 11.73 | -14.87 | TORSO_LOWER |
| p0365 | 70.71 | 4.09 | 10.49 | -14.71 | TORSO_LOWER |
| p0093 | 71.03 | 1.47 | 13.00 | -14.60 | TORSO_LOWER |

---

## D) Pattern histogram

**dominant_residual_key counts:**
| Key | Count |
|-----|-------|
| TORSO_UPPER | 2 |
| TORSO_MID | 171 |
| TORSO_LOWER | 211 |

**sign_pattern_histogram (BUST, WAIST, HIP):**
| Pattern | Count |
|---------|-------|
| +,+,- | 210 |
| -,+,- | 171 |
| -,-,+ | 1 |
| +,-,- | 1 |
| -,+,+ | 1 |

---

## E) Determinism subset check result

- **subset_ids:** p0000 .. p0009 (first 10, sorted)
- **hash_matches:** true
- **mismatches:** []
- **run_dir_1:** full run `run_20260207_162505`
- **run_dir_2:** subset run `determinism_subset_run2`

No mismatches; no patch required.

---

## F) STATUS generated snippet line added

```
[B03] 2026-02-07T16:31:49+09:00: Step4 beta_fit_v0 full k=384: run_dir=exports/runs/facts/beta_fit_v0/run_20260207_162505 summary sha256=bd76b0f0095d7dc7898a9484a9ccb65c743350ee6fbf11ff14e5d3e4ab964221 quality p50=79.18 p90=86.95 min=66.26 failures=0
```

---

*Branch `feat/step4-beta-fit-full-batch` merged via PR #10. Exports/ not committed.*
