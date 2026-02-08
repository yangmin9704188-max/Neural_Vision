# Refine04: HIP Measurement Definition / Pelvis-Frame A/B (facts-only)

## Method definition summary

- **world_y_band (current):** HIP band in world-Y percentile (y_min + 0.48–0.78 × y_range); max perimeter; tie-break by y.
- **pelvis_frame_band (new):** Pelvis-relative height h = dot(v − pelvis_origin, up_axis). Band [h_min + 0.48×h_range, h_min + 0.78×h_range]; max perimeter; tie-break by h closest to target then slice_index. Pelvis frame: joints "pelvis" if provided, else centroid of lower-torso band (y in [y_min+0.45×range, y_min+0.55×range]); up_axis = (0,1,0). Fallback: frame unavailable → "HIP_FRAME_FALLBACK_TO_WORLD_Y", use world_y_band.

## A/B evaluation (Top40 eval set)

| Metric | world_y_band (A) | pelvis_frame_band (B) |
|--------|------------------|------------------------|
| HIP p50 (cm) | -14.09 | -14.09 |
| HIP p90 (cm) | -13.46 | -13.46 |
| HIP max abs (cm) | 16.97 | 16.97 |
| WAIST p90 (cm) | 13.17 | 13.17 |
| BUST p90 (cm) | 5.18 | 5.18 |
| quality_p90 | 73.00 | 73.00 |

- **delta_p90_cm:** 0.0  
- **delta_abs_p90_cm:** 0.0  
- **waist_bust_unchanged:** true  
- **determinism_check.method_b_twice_identical:** true  

## Default changed?

**No.** Pelvis_frame_band did not improve |HIP p90| by ≥1.0 cm on the Top40 eval set (delta_abs_p90 = 0). Both methods produced identical HIP residuals on this set.

## Conclusion (facts-only)

- Pelvis-frame band (mesh-only pelvis proxy) gave the same HIP results as world_y_band on the HIP-hard eval set.
- Root cause of HIP residual is not resolved by this coordinate normalization alone; default remains **world_y_band**.
- Further improvement would require other changes (e.g. joint-based pelvis when available, or different landmark/band definition).
