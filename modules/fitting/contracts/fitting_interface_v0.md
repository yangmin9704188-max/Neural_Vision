# Fitting Interface — Contract (v1)

**Purpose**: Artifact-only interface for fitting operations. Enables U1 parallel work via frozen input/output contract. No implementation imports; all integration via file paths only.

**Schema Version**: `fitting_manifest.v1`  
**Contract reference**: `labs/specs/fitting_manifest.schema.json`; validation: `tools/validate_fitting_manifest.py`.

---

## Facts-Only / No PASS–FAIL

- **NO quality thresholds**: No pass/fail or score-based judgment (e.g. no `score_total < 70`). Report measurements and facts only.
- **NaN**: Allowed internally; serialized as `null` in JSON. No crash; output files are always produced.
- **No drop/clamp**: Do not drop or clamp values to improve metrics. Use `warnings` and facts to record conditions.

---

## Path Policy

- **All manifest and artifact paths**: Run-root–relative only. Absolute paths, drive-letter paths (e.g. `C:\...`), and `file://` are **not allowed** and are rejected by the validator.
- **Run root**: Directory containing the fitting manifest (or the `--run-dir` root when using the validator).
- **Resolution**: Every path in the manifest is resolved relative to run root. No cross-drive or absolute path usage.

---

## Manifest Structure (v1)

Canonical schema: `labs/specs/fitting_manifest.schema.json`. Summary below; field names and requirements must match the schema.

### Required Fields

| Field | Description |
|-------|-------------|
| `schema_version` | `"fitting_manifest.v1"` (const) |
| `contract_version` | Contract version string (e.g. `contract.v1`, `sizekorea_v2`) |
| `created_at` | ISO 8601 date-time; not used in `inputs_fingerprint` |
| `inputs_fingerprint` | Hex string (input-based only); length 32–128. Algorithm declared via `fingerprint_algo` |
| `fingerprint_algo` | Required when `inputs_fingerprint` present: `"sha256"` \| `"sha384"` \| `"sha512"` |
| `input_manifests` | See [Input Manifests](#input-manifests) |
| `limits` | See [Limits](#limits) |
| `camera` | See [Camera Preset](#camera-preset-fixed_camera_preset_v1) |
| `outputs` | See [Outputs](#outputs) |

### Input Manifests

- **`input_manifests.body_manifest_path`** (string): Relative path to body `geometry_manifest.json` (run root).
- **`input_manifests.garment_manifest_path`** (string): Relative path to garment `geometry_manifest.json` (run root).

Body and garment are specified **only** via these geometry manifest paths. Garment input priority (see [Garment Input Priority](#garment-input-priority)) is recorded in facts, not in the manifest.

### Garment Input Priority

- **Primary**: Garment proxy NPZ (when present and valid). Path/artifact follows geometry_manifest contract.
- **Fallback**: GLB + metadata when NPZ is not used. Which source was used must be recorded in `fitting_facts_summary.json` as **`garment_input_path_used`**: `"npz"` or `"glb_fallback"`.

### Limits

- **`limits.max_retry`**: `2` (const). Maximum number of retry attempts.
- **`limits.iter_max_per_attempt`**: `100` (const). Maximum iterations per attempt.

Enforced by schema and validator.

### Camera Preset (fixed_camera_preset_v1)

- **`camera.camera_preset_id`**: `"fixed_camera_preset_v1"` (const).
- **`camera.params`**: All distances in **meters (m)**. Angles in degrees.
  - `fov_deg`: Field of view (degrees).
  - `camera_distance_m`: Camera distance (m).
  - `yaw_deg`, `pitch_deg`, `roll_deg`: Orientation (degrees).
  - `near_m`, `far_m`: Near/far clip plane (m).
  - `image_resolution_w`, `image_resolution_h`: Image size (pixels).

**Open risk**: Exact numeric values for this preset are not frozen here; a separate canonical document may be required.

### Outputs

- **Required**:
  - **`outputs.geometry_manifest_path`**: Relative path to fitting output `geometry_manifest.json` (run root).
  - **`outputs.fitting_facts_summary_path`**: Relative path to fitting facts summary JSON (run root).
- **Optional** (all relative to run root):
  - `outputs.fit_signal_path`
  - `outputs.fitted_proxy_path`
  - `outputs.condition_images_dir`
  - `outputs.provenance_path`

### Optional Manifest Fields

- **`version_keys`**: `snapshot_version`, `semantic_version`, `geometry_impl_version`, `dataset_version`. Use `"UNSPECIFIED"` when unknown; validator may warn.
- **`warnings`**: Array of `{ code, severity, message }` from manifest producer.

---

## Geometry Manifest Reference

- The **geometry_manifest** schema (`contracts/geometry_manifest.schema.json`) has **`additionalProperties: false`** and is **not** extended by the fitting contract.
- Fitting refers to body and garment only by **path**: `input_manifests.body_manifest_path` and `input_manifests.garment_manifest_path` point to existing geometry_manifest JSON files. Fitting-specific metadata lives in the fitting manifest and in fitting outputs (e.g. `fitting_facts_summary.json`), not inside the geometry_manifest payload.

---

## Early Exit, Retry, and Iteration

- **Hard gate (e.g. garment-meta–based)**: Conditions such as `negative_face_area_flag` or `invalid_face_flag` cause **immediate early exit** with **no retry**. Result is recorded in facts (`early_exit`, `early_exit_reason`, `degraded_state`).
- **Smoke-2 (Garment Hard Gate)**:
  - Input: `garment_proxy_meta.json` with `negative_face_area_flag`, `self_intersection_flag`, or `invalid_face_flag` (OR logic).
  - Output: `fitting_facts_summary.json` must record:
    - `early_exit: true`
    - `early_exit_reason`: "garment_hard_gate_violation: <flag_names>"
    - `garment_input_path_used`: "npz" | "glb_fallback"
- **Retry**: Subject to **limits**: max **2** retries, **100** iterations per attempt. These are the canonical contract values (schema and validator).

---

## 결측 처리 골격 (Missing / Degraded Handling — Contract Only)

Defines the **minimum shape** of `fitting_facts_summary.json` (v1) for missing data and degraded runs. Implementation details are out of scope; only the contract is specified here.

### fitting_facts_summary.json (v1) — Minimum Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | e.g. `"fitting_facts_summary.v1"` |
| `garment_input_path_used` | string | `"npz"` \| `"glb_fallback"` — which garment source was used |
| `early_exit` | boolean | Whether the run ended by early exit (e.g. hard gate) |
| `early_exit_reason` | string \| null | Reason code or message when `early_exit` is true |
| `degraded_state` | object \| array | Records causes of missing/partial failure (structure TBD per implementation; presence is contract) |
| `warnings_summary` | object | `dict[CODE] -> { count: int, sample_messages: [≤5 strings], truncated: bool }` |

Existing fact fields (e.g. coverage, nan counts, reasons) may be kept and aligned with v1 naming; v1 minimum above is mandatory. NaN in JSON is always serialized as `null`; output file creation is always performed (no crash on missing data).

---

## Version Keys (4 Keys)

All fitting artifacts should carry these four version keys (e.g. in provenance or version_keys). Unknown values use `"UNSPECIFIED"`.

| Key | Description |
|-----|-------------|
| `snapshot_version` | Point-in-time snapshot identifier |
| `semantic_version` | Semantic version string |
| `geometry_impl_version` | Geometry implementation version |
| `dataset_version` | Dataset version |

---

## Key Space (Facts / Measurements)

**Standard body measurement keys** (meters): e.g. `BUST_CIRC_M`, `WAIST_CIRC_M`, `HIP_CIRC_M`. Mapping from simple keys (e.g. `bust`) to standard keys is recorded as fact (e.g. in `fitting_facts_summary` or equivalent). No filtering or quality judgment.

---

## Run-dir Strict Validation (U1 Gate)

Strict-run mode enforces U1 contract compliance via evidence-based checks. Scope: **existence, schema, path policy only**. No quality thresholds or score-based judgment.

### Definition

- **Purpose**: U1 contract enforcement (evidence-based).
- **Scope**: Existence of required artifacts, schema compliance, path policy. No quality pass/fail thresholds.
- **Tool**: `tools/validate_fitting_manifest.py --run-dir <dir> --strict-run`.

### Required Four Paths (FAIL if missing)

| Path | Description |
|------|-------------|
| `input_manifests.body_manifest_path` | Body geometry manifest |
| `input_manifests.garment_manifest_path` | Garment geometry manifest |
| `outputs.geometry_manifest_path` | Fitting output geometry manifest |
| `outputs.fitting_facts_summary_path` | Fitting facts summary (v1) |

### Chain Validation

When files exist:

- **Geometry manifests** (body, garment, output) → `contracts/geometry_manifest.schema.json`
- **Facts summary** → `tools/validate_fitting_facts_summary.py` (fitting_facts_summary.v1 schema)

### Suite Result Interpretation (facts-only)

- v1 manifests pass; v0 manifests fail (`schema_version must be 'fitting_manifest.v1'`).
- Absolute paths in body/garment manifest paths cause FAIL (`not a relative path`).
- strict-run detects `required file missing` for outputs.fitting_facts_summary_path or other required paths.
- Multiple fitting_manifest.v1 candidates in run-dir cause FAIL; use single `fitting_manifest.json` or one manifest file.

### U1 Minimal Artifacts Gate (Freeze v1)

In addition to the four required paths, strict-run enforces U1 minimal artifact existence (existence/format only; no quality thresholds):

- **Body input manifest** (`input_manifests.body_manifest_path`): Must have body subset file **`body_measurements_subset.json`** (single filename freeze). Path may appear in artifacts or at run root. If found, format is validated: `unit == "m"`, `pose_id == "PZ1"`, canonical 3 keys present (BUST_CIRC_M, WAIST_CIRC_M, HIP_CIRC_M or aliases).
- **Garment input manifest**: See [Garment Artifacts Binding (Freeze v1)](#garment-artifacts-binding-freeze-v1) below.
- Paths are resolved relative to run root. Existence is checked via file system; no content validation beyond body subset format.
- **Legacy compatibility**: Other body subset filenames are not supported for U1; strict-run enforces only `body_measurements_subset.json`. Filename changes require v2 contract.

### Garment Artifacts Binding (Freeze v1)

Strict-run checks garment input via **artifacts field** (not basename). geometry_manifest artifacts semantics:

- **artifacts.npz_path**: Garment proxy NPZ (optional, recommended). If present and file exists → PASS (NPZ path).
- **artifacts.mesh_path**: Garment proxy GLB (required for fallback).
- **artifacts.measurements_path**: Garment proxy META JSON (required for fallback).
- **artifacts.aux_paths**: Additional auxiliary files (optional).

Rules: npz_path file exists → PASS. Else: mesh_path + measurements_path both present and both files exist → PASS (GLB+META fallback). Otherwise FAIL. Fitting strict-run requires run-root-relative paths only (overrides geometry_manifest schema’s absolute-path allowance).

### Operational Commands

```bash
py tools/run_manifest_validation_suite.py --strict-run
```

```bash
py tools/validate_fitting_manifest.py --run-dir runs/smoke_test_strict_pass --strict-run
```

```bash
py tools/validate_fitting_manifest.py --run-dir runs/smoke_test_missing_facts_summary --strict-run
```

---

## Integration Rules

- **Path-only communication**: All inputs and outputs via file paths (relative to run root).
- **Facts-only**: Report what is; no pass/fail thresholds. Use `warnings_summary` and facts.
- **NaN tolerance**: NaN serialized as `null` in JSON; do not drop or clamp to improve metrics.
- **No cross-module implementation imports**: Integration via artifacts and paths only.

---

## Minimal Example (v1)

```json
{
  "schema_version": "fitting_manifest.v1",
  "contract_version": "contract.v1",
  "created_at": "2025-02-07T12:00:00Z",
  "inputs_fingerprint": "a1b2c3d4e5f6789012345678901234567890abcd",
  "fingerprint_algo": "sha256",
  "input_manifests": {
    "body_manifest_path": "body_geometry_manifest.json",
    "garment_manifest_path": "garment_geometry_manifest.json"
  },
  "limits": { "max_retry": 2, "iter_max_per_attempt": 100 },
  "camera": {
    "camera_preset_id": "fixed_camera_preset_v1",
    "params": {
      "fov_deg": 45,
      "camera_distance_m": 2.0,
      "yaw_deg": 0,
      "pitch_deg": -10,
      "roll_deg": 0,
      "near_m": 0.1,
      "far_m": 10.0,
      "image_resolution_w": 1920,
      "image_resolution_h": 1080
    }
  },
  "outputs": {
    "geometry_manifest_path": "output/geometry_manifest.json",
    "fitting_facts_summary_path": "output/fitting_facts_summary.json"
  }
}
```

---

## Legacy / Non-Canonical (v0 Runner Conventions)

The following are **not** part of the v1 contract and are kept only for reference:

- **`out_dir`** / **`expected_files`**: v0 runner-centric output layout. In v1, outputs are specified by explicit paths in `outputs.*` (e.g. `geometry_manifest_path`, `fitting_facts_summary_path`). Use run-root–relative paths only.
- **`path_base`** / **`manifest_dir`** vs **`run_dir`**: v1 assumes a single run root for all relative paths; absolute path usage is disallowed.
