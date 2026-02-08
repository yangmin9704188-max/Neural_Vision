# Refine02: HIP Band Sweep Comparison (facts-only)

## Selection

| config_id | hip_band | tie_break | HIP p90 (cm) | WAIST p90 (cm) | BUST p90 (cm) | quality_p90 | notes |
|-----------|----------|-----------|--------------|----------------|---------------|-------------|-------|
| A | 0.50–0.80 | prefer_lower_y | -9.07 | 10.55 | 0.75 | 81.62 | baseline |
| B | 0.48–0.78 | prefer_lower_y | -9.07 | 10.55 | 0.75 | 81.62 | refine01 default |
| C | 0.50–0.78 | prefer_lower_y | -9.07 | 10.55 | 0.75 | 81.62 | |
| D | 0.52–0.80 | prefer_lower_y | -9.07 | 10.55 | 0.75 | 81.62 | |
| E | 0.46–0.76 | prefer_lower_y | -9.07 | 10.55 | 0.75 | 81.62 | |
| B_high | 0.48–0.78 | prefer_higher_y | -9.07 | 10.55 | 0.75 | 81.62 | |

## Selection rule (facts-only, deterministic)

- Prefer config that minimizes |HIP p90| while:
  - WAIST p90 not worse by > 1 cm vs refine01 (B)
  - BUST p90 not worse by > 0.5 cm vs refine01 (B)

## Result

All configs tied (identical residuals on k=10 dev set). **B (refine01)** retained as default.

## WAIST/BUST regression check

- WAIST p90: 10.55 (refine01); all configs = 10.55 (no regression)
- BUST p90: 0.75 (refine01); all configs = 0.75 (no regression)
