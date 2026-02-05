> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 46

## Goal
Expand manifest coverage from 5 to 20 mesh_path-enabled cases (manual Tier2 backfill) for better statistical validation.

## Changes
- **Manifest Coverage Expansion**:
  - Created `verification/manifests/s1_manifest_v0_round46.json` with 15 additional enabled cases
  - Selected 15 case_ids from existing manifest (where mesh_path was null) and assigned known-good OBJ files
  - OBJ assignment: 5 cases each for `6th_20M.obj`, `6th_30M.obj`, `6th_40M.obj`
  - Selected case_ids: `211608191617`, `21_F_6338`, `121607180555`, `21_F_5759`, `20_F_3012`, `20_M_2444`, `20_M_0969`, `111609012195`, `20_M_0356`, `21_F_3588`, `20_F_0723`, `20_M_3296`, `21_F_6076`, `21_F_6854`, `20_F_3016`
- **Runner Configuration**:
  - Runner accepts `--manifest` argument to specify manifest file
  - Round46 uses `verification/manifests/s1_manifest_v0_round46.json` instead of default `s1_manifest_v0.json`
  - No code changes required; manifest path passed via CLI argument

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round46_20260127_193650`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round46_20260127_193650/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round46_20260127_193650/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round46_20260127_193650/KPI_DIFF.md`

## PR Link
[Round46 PR link to be added]

## Notes
- **Run Statistics**: total_cases=200, processed=20, skipped=180, has_mesh_path_true=20, has_mesh_path_null=180
- **Coverage Expansion**: Successfully expanded from 5 to 20 processed cases (4x increase)
- **Torso Keys NaN Rate**: 0.0 for NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M (all 20 cases have numeric values)
- **Failure Reasons TopK**: `SINGLE_COMPONENT_ONLY=20` (all 20 processed cases)
- **Torso Diagnostics Summary**: Present with `n_intersection_points_summary`, `n_segments_summary`, `n_components_summary` for NECK_CIRC_M, BUST_CIRC_M, UNDERBUST_CIRC_M
- **Scale Warnings**: 20 cases had mm->m conversion (expected for proxy OBJ files)
- **Backfill Log**: Entry added to `docs/ops/BACKFILL_LOG.md` documenting manual Tier2 backfill process
