# geo_v0_s1 Contract v0 (Interface Lock)

**Status**: Active (2026-01-28)
**Lane**: geo_v0_s1
**Purpose**: Lock input/output schema and keyset to prevent semantic drift

## 1. Units and Scale

### Canonical Units
- **Length/Circumference**: meters (m)
- **Area**: square meters (m²)
- **Precision**: 0.001m (1mm)

### Scale Conversion Policy
- **mm → m conversion**: Allowed and must be recorded
- **Fact recording**: Log as `SCALE_ASSUMED_MM_TO_M` in warnings or failure_reasons
- **No silent conversion**: All scale assumptions must be observable in output artifacts

**Rationale**: Round70 and prior rounds observed recurring scale conversion logs. This policy ensures conversions are traceable without being treated as errors.

## 2. Keyset Contract

### 2.1 Guaranteed Core Keys (Stable)

These keys MUST be present in output when extraction succeeds:

- `HEIGHT_M`
- `BUST_CIRC_M`
- `UNDERBUST_CIRC_M`
- `WAIST_CIRC_M`
- `HIP_CIRC_M`

**Guarantee**: These keys are considered stable across all geo_v0_s1 rounds.

### 2.2 Guaranteed Torso Keys (Stable After Round46+)

These keys are guaranteed when torso method is used (Round46+ boundary recovery):

- `NECK_CIRC_TORSO_M`
- `BUST_CIRC_TORSO_M`
- `UNDERBUST_CIRC_TORSO_M`

**Context**: Torso-based extraction provides alternative measurement path when full-body extraction encounters component constraints.

### 2.3 Optional Keys (May Appear)

These keys may appear depending on mesh geometry and extraction success, but are not guaranteed:

- `WAIST_WIDTH_M`
- `WAIST_DEPTH_M`
- `HIP_WIDTH_M`
- `HIP_DEPTH_M`
- `BUST_WIDTH_M`
- `BUST_DEPTH_M`
- `SHOULDER_WIDTH_M`
- `ARM_LENGTH_M`
- `LEG_LENGTH_M`

**Policy**: Do not add new optional keys without documentation. Optional keys must not break downstream when absent.

### 2.4 Deprecated/Forbidden Keys

**CHEST_* keys**: DO NOT USE in geo_v0_s1.

**Historical note**: If "chest" semantics existed in earlier systems, they are considered split into:
- `BUST_CIRC_M` (fullest point of bust)
- `UNDERBUST_CIRC_M` (band measurement below bust)

This is a historical clarification, not an alias. New code must not introduce CHEST_* keys.

## 3. Input Manifest Contract

### 3.1 Schema
- **Format**: JSON
- **Schema version**: `s1_mesh_v0@1`
- **Required fields per case**:
  - `case_id` (string, unique within manifest)
  - `mesh_path` (string or null)

### 3.2 case_id Uniqueness

**Requirement**: `case_id` MUST be unique within a single manifest.

**Duplicate handling policy**:
1. If duplicates exist, runner must use dict-based accounting (keyed by case_id)
2. Duplicates are treated as a **manifest data quality issue** (not a code bug)
3. Observability MUST expose duplicate counts in facts_summary
4. Remediation: Create a NEW manifest that deduplicates deterministically (keep-first, drop-later)
5. DO NOT modify original manifest files

**Example**: Round70 manifest deduplication (facts-only):
- Input: `s1_manifest_v0_round64.json` (200 entries, 199 unique, 1 duplicate: `20_F_3012` appeared 2 times)
- Output: `s1_manifest_v0_round70.json` (199 entries, 199 unique, 0 duplicates)
- Dedup rule: Keep first occurrence, drop later duplicates
- Result: `total_cases=199`, `manifest_duplicate_case_id_count=0`

### 3.3 Manifest Evolution
- New manifests should use sequential versioning: `s1_manifest_v0_roundXX.json`
- Each new manifest file is append-only to repo history
- Document manifest provenance in round notes

## 4. Output Contract (facts_summary.json)

### 4.1 Mandatory Top-Level Fields

These fields MUST be present in every facts_summary.json:

- `total_cases` (int): Number of cases in manifest
- `processed_cases` (int): Cases successfully processed (extraction succeeded)
- `skipped_cases` (int): Cases skipped (e.g., null mesh_path, load failure)
- `has_mesh_path_true` (int): Cases with non-null mesh_path
- `has_mesh_path_null` (int): Cases with null mesh_path
- `skip_reasons` (object): Aggregated skip reason counts

### 4.2 Key-Level Statistics

For each measurement key present in outputs:

- **NaN rate**: Percentage of cases where key is NaN
- **Distribution stats**: min, max, mean, p50, p95 (when not NaN)
- **Top-K reporting**: Report top5 keys by NaN rate

**Policy**: NaN is a valid measurement state (indicates extraction did not produce that key for that case). NaN rate is a signal, not a failure.

### 4.3 Observability Fields (Always Emit)

These fields MUST be present even when counts are zero:

**Torso observability**:
- `torso_method_used_count` (int)
- `alpha_fail_reasons_topk` (dict)

**Boundary recovery observability**:
- `boundary_recovery_used_count` (int)
- `boundary_recovery_success_count` (int)

**Execution failure observability** (Round66+):
- `exec_fail_count` (int)
- `exec_fail_reason_topk` (dict)
- `exec_fail_case_ids_sample` (list, max 3)

**Processed sink observability** (Round66+):
- `processed_sink_count` (int)
- `processed_sink_reason_topk` (dict)
- `processed_sink_case_ids_sample` (list, max 3)

**Success-not-processed observability** (Round67+):
- `success_logged_count` (int)
- `success_not_processed_count` (int)
- `success_not_processed_reason_topk` (dict)
- `success_not_processed_case_ids_sample` (list, max 3)

**Record missing observability** (Round68+):
- `record_expected_total` (int)
- `record_actual_total` (int)
- `record_missing_count` (int)
- `record_missing_case_ids_sample` (list, max 3)

**Manifest duplicate observability** (Round69+):
- `manifest_total_entries` (int)
- `manifest_unique_case_ids` (int)
- `manifest_duplicate_case_id_count` (int)
- `manifest_duplicate_case_id_topk` (dict)
- `manifest_duplicate_case_ids_sample` (list, max 3)

**Policy**: These fields are **signals only**, never PASS/FAIL judgments. They exist to surface data quality and execution issues for human review.

### 4.4 Output Artifact Guarantees

- `facts_summary.json`: Always generated
- `skip_reasons.jsonl`: JSONL file with one record per skipped case
- `exec_failures.jsonl`: JSONL file when exec_fail_count > 0
- `processed_sink.jsonl`: JSONL file when processed_sink_count > 0
- `success_not_processed.jsonl`: JSONL file when success_not_processed_count > 0

## 5. Semantic Stability Rules

### 5.1 Key Naming
- Use `_M` suffix for meter-unit keys
- Use `_CIRC_` for circumference measurements
- Use `_WIDTH_` and `_DEPTH_` for orthogonal dimensions
- Do NOT create ambiguous names (e.g., CHEST vs BUST)

### 5.2 Key Addition Policy
- New guaranteed keys require contract version bump
- New optional keys require documentation in this contract
- Deprecated keys must be listed in section 2.4

### 5.3 Breaking Changes
- Removing guaranteed keys = breaking change (requires major version)
- Changing key semantics = breaking change (requires major version)
- Adding observability fields = non-breaking (additive only)

## 6. Validation and Compliance

### 6.1 Contract Verification
- KPI reports should reference this contract for key expectations
- Postprocessing tools should validate facts_summary schema compliance
- Round documentation should note any deviations from contract

### 6.2 Evolution Path
- This is contract **v0** (initial lock)
- Future versions: `geo_v0_s1_contract_v1.md`, etc.
- Breaking changes require new contract version document

## 7. References

- **Round46**: Torso method introduction and boundary recovery
- **Round66**: Processed sink observability (exec_fail wiring)
- **Round67**: Success-not-processed observability
- **Round68**: Record missing observability, duplicate case_id discovery
- **Round69**: Manifest duplicate observability
- **Round70**: Manifest deduplication (200→199 cases, 1 duplicate removed)

## Appendix: Round70 Contract Validation (Facts-Only)

Round70 demonstrated contract compliance after manifest deduplication:

**Input Manifest**: `s1_manifest_v0_round70.json`
- manifest_total_entries: 199
- manifest_unique_case_ids: 199
- manifest_duplicate_case_id_count: 0

**Run Statistics**:
- total_cases: 199
- processed_cases: 199
- skipped_cases: 0
- has_mesh_path_true: 199
- has_mesh_path_null: 0

**Observability (Clean State)**:
- exec_fail_count: 0
- processed_sink_count: 0
- success_not_processed_count: 0
- record_missing_count: 0
- manifest_duplicate_case_id_count: 0

**Key Distribution Stability**:
- HEIGHT_M p50: 1.7283m (stable vs Round69)
- BUST_CIRC_M p50: 1.7273m (stable vs Round69)
- WAIST_CIRC_M p50: 1.3086m (stable vs Round69)
- HIP_CIRC_M p50: 1.6363m (stable vs Round69)

All guaranteed core keys present with 0.00% NaN rate.
