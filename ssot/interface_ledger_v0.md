# Interface Ledger v0 (Cross-Module)

**Status**: CANONICAL  
**Purpose**: Single source of truth for artifact interfaces across body / fitting / garment modules.  
**Facts-only**: No PASS/FAIL. No thresholds/clamps. Evidence-first: file existence is top DoD.

---

## Canon Decisions (LOCKED)

### Path Policy: C
- ABS paths: allowed
- REL paths: allowed
- Canonical REL base: **manifest_dir** (directory containing the manifest file)
- Legacy REL base: **run_dir** allowed **only if explicitly signaled** in provenance

**Provenance MUST include (when REL used):**
- `path_base`: `"manifest_dir"` or `"run_dir"`
- `manifest_path`: absolute path to the manifest file (anchor for REL resolution)

### Naming Policy: B
- Body output: `facts_summary.json`
- Fitting output: **`fitting_facts_summary.json`** (NOT `facts_summary.json`) to prevent collision

### Version Policy: C (LOCKED)
All cross-module artifacts MUST carry the **same 4 version keys**:

| Key | Meaning | If Unknown |
|---|---|---|
| `snapshot_version` | snapshot/release anchor | `"UNSPECIFIED"` + warning `VERSION_KEY_UNSPECIFIED` |
| `semantic_version` | semantic definition version | `"UNSPECIFIED"` + warning `VERSION_KEY_UNSPECIFIED` |
| `geometry_impl_version` | geometry implementation version | `"UNSPECIFIED"` + warning `VERSION_KEY_UNSPECIFIED` |
| `dataset_version` | dataset version | `"UNSPECIFIED"` + warning `VERSION_KEY_UNSPECIFIED` |

Notes:
- `schema_version` is **separate**: it identifies each artifact/schema (e.g., `fitting_manifest.v0`) and remains required where applicable.
- If any of the 4 keys is unknown at runtime, it MUST still exist with `"UNSPECIFIED"` and record warning code `VERSION_KEY_UNSPECIFIED`.

---

## Global Invariants (LOCKED)
- Units: **meters (m)** only. No scale correction. Suspicion ⇒ warning only.
- NaN/Inf: allowed internally; JSON serialization MUST be **null**.
- Always-emit: required artifacts MUST be created even if values are null/empty.
- Warnings canonical format (explosion-safe):
  - `warnings[CODE] = {count:int, sample_messages:[<=5 strings], truncated:bool}`
  - Legacy/inner-run may use `warnings[CODE] = [string...]` but cross-module outputs SHOULD use canonical.

---

## Round / Milestone Policy (LOCKED)
- Lane format: `module/<lane_id>`  
  Examples: `body/geo_v0_s1`, `fitting/fitting_v0_facts`, `garment/garment_v0_x`

- Milestone format: `MNN_<short_tag>` (tag 자유, 형식 고정)  
  Examples: `M01_alpha`, `M02_beta`, `M03_final`

- RID: `lane_slug__milestone_id__rNN` (NN=2-digit, 01~99)
  - `lane_slug` = lane with `/` replaced by `-`
  - Example: `body-geo_v0_s1__M01_alpha__r01`

- Round docs path (NEW rounds, append-only):
  - `docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md`

- Legacy rounds:
  - existing `docs/ops/rounds/roundXX.md` are **LEGACY NAMING**
  - do not rewrite content; prepend LEGACY stamp only

---

## Cross-Module Interfaces (File-Level)

| Producer | Consumer | Kind | Canonical Location | Required | Format | Path Rule | Version Keys | Units | NaN |
|---|---|---|---|---:|---|---|---|---|---|
| body/geo_v0_s1 | fitting | body facts summary (input) | `<body_run_dir>/facts_summary.json` | yes | json | ABS or REL-to-manifest | 4 keys | m | null |
| fitting/fitting_v0_facts | ops/review | fitting summary (output) | `<fitting_run_dir>/fitting_summary.json` | yes | json | REL-to-manifest | 4 keys | m | null |
| fitting/fitting_v0_facts | ops/review | fitting facts (output) | `<fitting_run_dir>/fitting_facts_summary.json` | yes | json | REL-to-manifest | 4 keys | m | null |
| body/geo_v0_s1 | ops/review | KPI / KPI_DIFF | `<run_dir>/KPI.md`, `<run_dir>/KPI_DIFF.md` | yes | md | legacy ok | (legacy partial ok) | m | - |
| body/geo_v0_s1 | ops/review | LINEAGE | `<run_dir>/LINEAGE.md` | yes | md | legacy ok | (legacy partial ok) | - | - |

---

## Optional: Ledger Row Export (Candidate-Only, NOT auto-editing canonical)
Agents MAY emit candidate rows per run:
- `artifacts/interface_ledger_rows.jsonl`

Each JSONL row SHOULD include:
- producer, consumer, kind
- produced_paths (array of strings)
- required_files_present (bool + missing list)
- path_base_used ("manifest_dir"|"run_dir")
- manifest_path (abs)
- schema_version
- 4 version keys (with UNSPECIFIED allowed)
- units ("m")
- nan_serialization ("null")
- warnings_format ("canonical"|"legacy_array")
