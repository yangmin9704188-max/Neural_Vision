> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 45

## Goal
Make torso-only channel produce at least one numeric value even when failure_reason is SINGLE_COMPONENT_ONLY, and keep facts-only signals.

## Changes
- **core/measurements/core_measurements_v0.py**:
  - Round45: When failure_reason == SINGLE_COMPONENT_ONLY and torso_perimeter is None, compute perimeter from the single component as fallback (ordering -> unordered -> hull).
  - Set TORSO_SINGLE_COMPONENT_FALLBACK_USED flag when this fallback is used.

- **verification/runners/run_geo_v0_s1_facts.py**:
  - Round45: Aggregate TORSO_SINGLE_COMPONENT_FALLBACK_USED (per case/key).
  - Round45: Add torso_debug_stats_summary to facts_summary: per-key area/perimeter/circularity_proxy (perimeter^2/area) summary stats (p50/p95) for processed cases.

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round45_20260127_191401`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round45_20260127_191401/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round45_20260127_191401/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round45_20260127_191401/KPI_DIFF.md`

## PR Link
[Round45 PR link to be added]

## Notes
- Torso keys (NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M) all have nan_count 0 (values emitted for all 5 cases).
- TORSO_SINGLE_COMPONENT_FALLBACK_USED count: 0 (fallback not triggered in this run; normal perimeter computation path succeeded even for single-component cases).
- torso_debug_stats_summary added: area/perimeter/circularity_proxy stats (p50/p95) per key.
- Full keys (*_CIRC_M) unchanged.
