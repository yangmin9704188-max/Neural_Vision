# Refine03: HIP Eval-Set Sweep (facts-only)

## N and selection rule

- **N:** 40
- **Selection rule:** `topN_abs_hip_residual` — top 40 prototypes by |HIP residual cm| from Step4 full run; tie-break by `prototype_id` lexicographic.
- **Eval set source:** Step4 full run (beta_fit_v0 run_dir with k=384).

## hip_sweep_eval_report summary

| config_id | HIP p90 (cm) | \|HIP p90\| | WAIST p90 (cm) | BUST p90 (cm) | quality_p90 |
|-----------|--------------|-------------|----------------|---------------|-------------|
| A | -13.46 | 13.46 | 13.17 | 5.18 | 73.00 |
| B | -13.46 | 13.46 | 13.17 | 5.18 | 73.00 |
| C | -13.46 | 13.46 | 13.17 | 5.18 | 73.00 |
| D | -16.18 | 16.18 | 13.17 | 5.18 | 73.00 |
| E | -13.46 | 13.46 | 13.17 | 5.18 | 73.00 |
| B_high | -13.46 | 13.46 | 13.17 | 5.18 | 73.00 |

- **Do configs differ?** Yes. D has larger |HIP p90| (16.18 vs 13.46). A, B, C, E, B_high are identical.
- **Best config (by |HIP p90|):** A, B, C, E, B_high (tie). B is current default (refine01).

## Conclusion

- **No sensitivity to band/tie-break among A,B,C,E,B_high:** On the HIP-hard eval set (top 40 by |HIP|), configs A, B, C, E, B_high yield identical HIP residuals. Config D worsens |HIP p90|.
- **No default change:** B (refine01) retained.
- **Escalate to refine04:** HIP band/tie-break does not improve residuals on this eval set. Next step: investigate measurement definition / coordinate normalization (e.g. plane selection, contour extraction, torso-only masking).

## WAIST/BUST

- WAIST p90 and BUST p90 are from fit_result residuals (same for all configs). No regression.
