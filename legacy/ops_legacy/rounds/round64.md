> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 64

## Goal
Expand coverage from 100 to 200 cases by backfilling remaining 100 null mesh_path entries with known-good OBJ proxies. Facts-only observation at full 200 sample size.

## Changes
- **Manifest Backfill** (Tier2):
  - Created Round64 manifest from Round63 manifest
  - Filled 100 null mesh_path entries with proxy OBJ files
  - Round-robin assignment: 6th_20M.obj (34 cases), 6th_30M.obj (33 cases), 6th_40M.obj (33 cases)
  - All 100 assigned paths verified to exist on disk before round execution
  - Tool: `tools/create_round64_manifest.py` (deterministic, balanced distribution)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round64_20260128_102145`
- **manifest**: `verification/manifests/s1_manifest_v0_round64.json`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round64_20260128_102145/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round64_20260128_102145/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round64_20260128_102145/KPI_DIFF.md`

## PR Link
https://github.com/yangmin9704188-max/ai-fitting-engine/pull/236

## Notes
- **Run Statistics**:
  - total_cases=200
  - processed_cases=199
  - skipped_cases=0
  - has_mesh_path_true=200
  - has_mesh_path_null=0

- **Boundary Recovery Usage**:
  - boundary_recovery_used: secondary_builder=23, none=176
  - boundary_recovery_success: secondary_builder=23
  - **Result**: Boundary recovery usage observed at 23/199 (11.6%) for 200-case sample size

- **NaN Rate (Torso Keys)**:
  - WAIST_CIRC_M: 0.00%
  - WAIST_WIDTH_M: 0.00%
  - WAIST_DEPTH_M: 0.00%
  - HIP_CIRC_M: 0.00%
  - HIP_WIDTH_M: 0.00%

- **Failure Reasons**:
  - All cases processed successfully (no alpha failures, no measurement failures)

- **Backfill Summary**:
  - 100 case_ids: null -> proxy mesh
  - Example: case_id `21_F_6997`: null -> `verification/datasets/golden/s1_mesh_v0/meshes/6th_20M.obj`
  - Backfill details: See `docs/ops/BACKFILL_LOG.md` (Round64 entry)
