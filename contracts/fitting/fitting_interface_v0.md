# Fitting Interface v0

**Purpose**: Artifact-only interface for fitting operations. No implementation imports; all integration via file paths only.

**Schema Version**: `fitting_manifest.v0`

---

## Manifest Structure

### Required Fields

#### `schema_version` (string, const)
- Value: `"fitting_manifest.v0"`

#### `inputs` (object)
- **`units`** (string, const): `"m"` (meters, required)
- **`body_source`** (object, oneOf exactly one, all paths minLength:1):
  - `geometry_manifest_path` (string)
  - `body_measurements_path` (string)
  - `body_mesh_path` (string)
- **`garment_source`** (object, oneOf exactly one, all paths minLength:1):
  - `garment_template_path` (string)
  - `garment_measurements_path` (string)

#### `outputs` (object)
- **`out_dir`** (string, required, minLength:1): Output directory path

#### `provenance` (object)
- **`schema_version`** (string, const): `"fitting_manifest.v0"`
- **`code_fingerprint`** (string, required, minLength:1): Code version identifier

### Optional Fields

#### `outputs` (continued)
- **`expected_files`** (object, optional):
  - `fitting_summary` (string, const): `"fitting_summary.json"`
  - `facts_summary` (string, const): `"facts_summary.json"`
- **`visual_proxy`** (array of strings, optional): Visual proxy output paths

#### `provenance` (continued)
- **`input_fingerprints`** (object, optional): Dict of input file fingerprints (string values)

---

## Output Files

### `fitting_summary.json`

**Schema Version**: `fitting_summary.v0`

**Structure**:
- `schema_version` (string): `"fitting_summary.v0"`
- `metrics` (object):
  - `bust_ease_ratio` (float or null)
  - `waist_ease_ratio` (float or null)
  - `hip_ease_ratio` (float or null)
- `warnings` (object): `dict[CODE] -> list[string]` (code-based keys, e.g., `MISSING_KEY`, `PARSE_FAIL`)
- `provenance` (object):
  - `manifest_path` (string)
  - `code_fingerprint` (string)

### `facts_summary.json`

**Schema Version**: `facts_summary.v0`

**Structure**:
- `schema_version` (string): `"facts_summary.v0"`
- `coverage` (object):
  - `has_body_measurements` (boolean)
  - `has_garment_measurements` (boolean)
  - `used_keys` (array of strings)
- `nan_count` (object):
  - `total` (int)
  - `nan` (int)
- `nan_rate` (float): Fraction of NaN values (0.0 to 1.0)
- `reasons` (object): Counts for `missing_input`, `parse_fail`, `zero_division`, `missing_key`
- `warnings` (object): `dict[CODE] -> list[string]` (code-based keys)
- `provenance` (object):
  - `manifest_path` (string)
  - `code_fingerprint` (string)

---

## Facts-Only Policy

**Core Principles**:
- **NO PASS/FAIL/Thresholds**: Report measurements and facts only
- **NaN Handling**: NaN allowed internally, serialized as `null` in JSON output
- **NO Drop/Clamp**: Never drop data or clamp values to improve metrics
- **Warnings Structure**: Use stable code keys (e.g., `MISSING_KEY`, `UNITS_MISMATCH`) with message lists
- **Explosion Prevention**: Warning messages limited per code (max ~100) with `"...(truncated)"` marker

---

## Minimal Example

```json
{
  "schema_version": "fitting_manifest.v0",
  "inputs": {
    "units": "m",
    "body_source": {
      "body_measurements_path": "data/body.json"
    },
    "garment_source": {
      "garment_measurements_path": "data/garment.json"
    }
  },
  "outputs": {
    "out_dir": "outputs/run_001"
  },
  "provenance": {
    "schema_version": "fitting_manifest.v0",
    "code_fingerprint": "abc123def456"
  }
}
```

---

## Integration Rules

- **No cross-module imports**: Do not import from `modules/body` or `modules/garment` implementation code
- **Path-only communication**: All inputs/outputs via file paths
- **Facts-only**: Report what is, not pass/fail. Use `warnings` and `reasons` fields
- **NaN tolerance**: Do not drop NaN values to inflate coverage metrics. NaN serialized as null in JSON
