# Fitting Module

## Purpose

Fitting module workspace for parallel experiments and body×garment combination analysis.

This workspace is designed for isolated experimental work (e.g., by Anti-gravity agent) without affecting mainline body/garment code.

## Rules

- **Fitting code lives here only**: All fitting-related logic, experiments, and outputs belong in this module
- **Schema reference only**: May reference body/garment schemas (specs) but MUST NOT import body/garment implementation code
- **No PR/merge from Anti-gravity**: Anti-gravity works here in isolation; commits and PRs are done by Cursor or Claude Code only
- **Output convention**: `modules/fitting/outputs/<run_id>/`

## Module Boundaries

According to LAYERS_v1.md and GUARDRAILS.md:
- `modules/fitting/**` may reference `modules/body/specs/**` and `modules/garment/specs/**`
- MUST NOT import from `modules/body/**` or `modules/garment/**` implementation code
- Cross-module communication via artifacts only

## Output Structure

```
modules/fitting/outputs/
├── <run_id_1>/
│   ├── manifest.json
│   ├── results/
│   └── reports/
└── <run_id_2>/
    └── ...
```

All fitting outputs (collision detection, drape simulation, fitting results) are stored under `outputs/<run_id>/`.

## Workflow

1. Anti-gravity performs experiments in this workspace
2. Outputs are generated to `modules/fitting/outputs/<run_id>/`
3. Results are reviewed and, if approved, integrated by Cursor or Claude Code
4. Integration may include creating PRs, updating docs, or promoting artifacts

## References

- [Architecture LAYERS_v1](../../docs/architecture/LAYERS_v1.md)
- [GUARDRAILS](../../docs/ops/GUARDRAILS.md)
- [Modules README](../README.md)
