# geometry_manifest.v1

**Canonical schema** for `geometry_manifest.json` produced by Body, Garment, and Fitting run outputs.

**Location**: `contracts/geometry_manifest_v1.schema.json`

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `schema_version` | const | `"geometry_manifest.v1"` |
| `module_name` | enum | `"body"` \| `"fitting"` \| `"garment"` |
| `contract_version` | string | Module contract version |
| `created_at` | string | `YYYY-MM-DDTHH:MM:SSZ` (UTC, no milliseconds) |
| `inputs_fingerprint` | string | Deterministic hash (excludes created_at) |
| `version_keys` | object | Required keys: `snapshot_version`, `semantic_version`, `geometry_impl_version`, `dataset_version` |
| `artifacts` | array | Run-dir-relative paths only (no leading `/`, no `..`, no drive letters) |

## Optional fields

- `warnings` (array of strings)
- `warnings_path` (relative path string)
- `provenance_path` (relative path string)

## Determinism rules

- `inputs_fingerprint` MUST NOT include `created_at` in its calculation.
- `created_at` changes MUST NOT change `inputs_fingerprint`.

## Example (Body stub)

```json
{
  "schema_version": "geometry_manifest.v1",
  "module_name": "body",
  "contract_version": "v0",
  "created_at": "2026-02-05T12:00:00Z",
  "inputs_fingerprint": "sha256:abc123...",
  "version_keys": {
    "snapshot_version": "unknown",
    "semantic_version": "unknown",
    "geometry_impl_version": "unknown",
    "dataset_version": "unknown"
  },
  "artifacts": ["body_mesh.npz", "body_measurements_subset.json", "facts_summary.json"],
  "warnings": ["GEOMETRY_MANIFEST_STUB"]
}
```
