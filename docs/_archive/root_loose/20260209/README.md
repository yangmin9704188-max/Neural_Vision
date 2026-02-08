# Root Loose Copies Archive — 2026-02-09

## Context
During Round 06 cleanup, root loose copies were processed:
- **7 files**: Identical to canonical → deleted
- **2 files**: Different from canonical → archived here

## Archived Files

### master_plan_v1.json
**Status**: ARCHIVED (outdated version)
**Canonical**: `contracts/master_plan_v1.json`
**Reason**: Root copy contains older schema (schema_version vs plan_version), different structure (artifacts/maturity_levels vs steps array). Canonical was updated in Round 03 to task graph format.
**Action**: Canonical is authoritative; root copy preserved for reference only.

### renderer_input_contract_v1.md
**Status**: ARCHIVED (minor clarification added to canonical)
**Canonical**: `contracts/renderer_input_contract_v1.md`
**Reason**: Canonical has minor clarification in lab_root description ("경로 해석:" prefix added). Content is substantively identical.
**Action**: Canonical is authoritative; root copy preserved for reference only.

## Deleted Files (Identical to Canonical)
1. `dependency_ledger_v1.json` → `contracts/dependency_ledger_v1.json`
2. `fitting_interface_v0.md` → `contracts/fitting/fitting_interface_v0.md`
3. `Garment_step.md` → `modules/garment/docs/Garment_step.md`
4. `NOTION_SYNC_v1.md` → `docs/ops/NOTION_SYNC_v1.md`
5. `OPS_SYSTEM_OVERVIEW_v1.md` → `docs/ops/OPS_SYSTEM_OVERVIEW_v1.md`
6. `repo_layout_policy_v1.md` → `ssot/repo_layout_policy_v1.md`
7. `u1_u2_dod_checklist_v0.md` → `ssot/u1_u2_dod_checklist_v0.md`

## Post-cleanup State
All references should now point to canonical locations only. Doctor WARN for loose copies should be eliminated.
