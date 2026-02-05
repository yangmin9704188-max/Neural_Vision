> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 60

## Goal
Scale coverage from 50 to 100 cases (Tier2 manual backfill) and observe boundary recovery usage rate at larger sample size (facts-only). No algorithm changes.

## Changes
- **Manifest Coverage Expansion**:
  - Created `verification/manifests/s1_manifest_v0_round60.json`
  - Expanded from 50 to 100 enabled cases
  - Kept existing 50 mesh_path-enabled cases from Round58/59
  - Added 50 new cases: selected first 50 null cases from Round58 manifest
  - OBJ assignment: Round-robin distribution across `6th_20M.obj` (17 cases), `6th_30M.obj` (17 cases), `6th_40M.obj` (16 cases)
  - New enabled case_ids (50): `21_F_6996`, `20_F_0882`, `20_F_0494`, `221608111273`, `211608221812`, `21_M_6330`, `21_M_6682`, `511607184667`, `121607270908`, `511610314830`, `21_M_3503`, `20_F_2186`, `321607265203`, `21_M_4168`, `21_M_5628`, `20_F_1028`, `111609232739`, `20_F_0005`, `121609032290`, `21_M_3426`, `421608075746`, `21_M_3572`, `20_M_2058`, `21_F_4515`, `21_M_5500`, `20_F_0179`, `121607180571`, `211608221803`, `20_F_1489`, `21_M_3342`, `21_F_5412`, `321609065463`, `20_M_3194`, `21_F_5205`, `20_F_1006`, `21_M_3366`, `20_F_2527`, `121608282084`, `21_M_6609`, `21_F_3610`, `21_M_3352`, `21_F_7256`, `21_F_3899`, `121607160406`, `121607180584`, `20_F_2636`, `20_M_1147`, `21_F_5680`, `21_M_4193`, `21_F_6999`

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round60_20260127_234000`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round60_20260127_234000/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round60_20260127_234000/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round60_20260127_234000/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/229

## Notes
- **Run Statistics**: total_cases=200, processed=50, skipped=150, has_mesh_path_true=100, has_mesh_path_null=100
- **Coverage**: Expanded from 50 to 100 enabled cases using Round60 manifest
- **Boundary Recovery Tracking**:
  - boundary_recovery_used_count: {secondary_builder: 6, none: 44}
  - boundary_recovery_success_count: {secondary_builder: 6}
- **Boundary Recovery Cohort Summary** (boundary_recovery_cohort_summary):
  - For each key (NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M):
    - recovery_used cohort: {torso_loop_area_m2: {p50, p95, count}, torso_loop_perimeter_m: {p50, p95, count}, torso_loop_shape_ratio: {p50, p95, count}, loop_validity_counts: {...}, count: n}
    - none cohort: {torso_loop_area_m2: {p50, p95, count}, torso_loop_perimeter_m: {p50, p95, count}, torso_loop_shape_ratio: {p50, p95, count}, loop_validity_counts: {...}, count: n}
  - Highlights (numbers only):
    - NECK_CIRC_M:
      - recovery_used: count=6, area_m2 p50=0.0287, perimeter_m p50=0.774, shape_ratio p50=20.87, validity=VALID:6
      - none: count=44, area_m2 p50=0.0200, perimeter_m p50=0.772, shape_ratio p50=30.39, validity=VALID:44
- **Alpha Fail Reasons TopK**: {} (empty, no alpha failures)
- **Torso Keys NaN Rate**: 0.0 (all torso keys have valid values)
