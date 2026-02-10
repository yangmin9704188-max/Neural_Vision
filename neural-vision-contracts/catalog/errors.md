# Gate / Warning / Error Code Catalog

This catalog defines all gate codes, warning codes, and error codes
used across the Neural Vision pipeline contracts.

## 1. Hard Gate Codes (Garment → Fitting)

Hard gate flags cause **immediate early exit** in the Fitting module.
When any flag is `true`, Fitting MUST abort processing and record the
early exit in `fitting_facts_summary.json`.

| Code | Source Artifact | Field | Trigger | Effect |
|------|----------------|-------|---------|--------|
| `HARD_GATE_NEGATIVE_FACE_AREA` | `garment_proxy_meta.json` | `negative_face_area_flag` | `true` | Early exit; garment mesh has negative face area |
| `HARD_GATE_SELF_INTERSECTION` | `garment_proxy_meta.json` | `self_intersection_flag` | `true` | Early exit; garment mesh has self-intersections |
| `HARD_GATE_INVALID_FACE` | `garment_proxy_meta.json` | `invalid_face_flag` | `true` | Early exit; garment mesh has degenerate/invalid faces |

### Hard Gate Traceability Rule

Even when a hard gate triggers early exit, the following artifacts MUST still be produced:
- `garment_proxy_meta.json` (with flag(s) set to `true`)
- `geometry_manifest.json` (with warnings reflecting the gate)

The following MAY be omitted on hard gate:
- `garment_proxy_mesh.glb`
- `garment_proxy.npz`

## 2. Body Measurement Warning Codes

Warnings emitted in `body_measurements_subset.json` → `warnings[]`
and reflected in `geometry_manifest.json` → `warnings[]`.

| Code | Trigger | Severity | Effect |
|------|---------|----------|--------|
| `MEASUREMENT_NULL_SOFT` | Exactly 1 of 3 required keys is `null` | soft | `degraded_state = "none"`, warning recorded |
| `MEASUREMENT_NULL_DEGRADED` | 2 or more of 3 required keys are `null` | high | `degraded_state = "high_warning_degraded"` |
| `VERSION_KEY_UNSPECIFIED:<key>` | A `version_keys` value is `"UNSPECIFIED"` | info | Warning recorded in manifest |
| `UNIT_FAIL` | Suspected unit mismatch (cm-like values) | warn | Warning recorded, no abort |
| `PERIMETER_LARGE` | Perimeter value exceeds plausible range | warn | Warning recorded, no abort |

### Null Policy (Body Measurements)

The 3 required measurement keys are: `BUST_CIRC_M`, `WAIST_CIRC_M`, `HIP_CIRC_M`.

- `NaN` is **forbidden** in JSON serialization. Use `null` instead.
- 1 null → soft warning → Fitting proceeds normally
- 2+ null → degraded state → Fitting proceeds with `degraded_state = "high_warning_degraded"`

## 3. Fitting Warning Codes

Warnings emitted in `fitting_facts_summary.json` → `warnings_summary[]`.

| Code | Trigger | Effect |
|------|---------|--------|
| `GARMENT_INPUT_FALLBACK` | `garment_proxy.npz` not found; fell back to `.glb` + meta | `garment_input_path_used = "glb_fallback"` |
| `EARLY_EXIT_HARD_GATE` | Garment hard gate flag detected | `early_exit = true` |
| `DEGRADED_BODY_MEASUREMENT` | Body measurement null count ≥ 2 | `degraded_state = "high_warning_degraded"` |

## 4. Geometry Manifest Warning Codes

Warnings emitted in any module's `geometry_manifest.json` → `warnings[]`.

| Code | Trigger | Effect |
|------|---------|--------|
| `VERSION_KEY_UNSPECIFIED:<key>` | `version_keys.<key>` set to `"UNSPECIFIED"` | Info-level warning |
| `ARTIFACT_PATH_ABSOLUTE` | Artifact path is absolute (forbidden) | Validation failure |
| `CREATED_AT_MILLISECONDS` | `created_at` contains milliseconds (forbidden) | Validation failure |
| `INPUTS_FINGERPRINT_NONDETERMINISTIC` | Fingerprint includes `created_at` | Validation failure |

## 5. Generation Warning Codes

Warnings emitted in `generation_delivery.json` → `warnings[]`.

| Code | Trigger | Effect |
|------|---------|--------|
| `GEN_PROVENANCE_MISSING_RUN_ID` | A `source_run_ids` field is empty | Warning recorded |
| `GEN_HANDOFF_PATH_MISSING` | A required `handoff_paths` field is empty | Warning recorded |

## 6. API Envelope Gate Codes

Used in the API response envelope `gate` field.

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `PASS` | 200 | All processing completed successfully |
| `HARD_GATE` | 200 | Processing halted by hard gate; partial result returned |
| `DEGRADED` | 200 | Processing completed with degraded quality |
| `VALIDATION_ERROR` | 422 | Request failed schema validation |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Non-Goals

- This catalog does NOT define pass/fail thresholds or scoring.
- Gate codes are observational facts, not quality judgments.
- Adding new codes is a PATCH-level change; removing/renaming is MAJOR.
