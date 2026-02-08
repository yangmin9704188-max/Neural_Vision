# Body Consumer Path Policy (v1)

**Scope**: Path policy when body geometry_manifest is consumed (e.g., by fitting). Facts-only.

---

## Schema vs Consumer Path Policy

- **geometry_manifest.schema.json**: Defines payload shape only. Path fields (mesh_path, measurements_path, npz_path, aux_paths) are string; schema does not enforce absolute vs relative.
- **Consumer policy override**: The consumer (e.g., fitting) may impose stricter rules. Consumer policy takes precedence over schema allowance when enforced.
- **Round K principle**: Path allowance (absolute vs relative) may be restricted by consumer policies. See `contracts/GEOMETRY_MANIFEST_PATH_POLICY.md`.

---

## Run-Root-Relative Only (Consumer Policy)

When fitting consumes body geometry_manifest (strict-run):

- **Allowed**: Run-root-relative paths only.
- **Disallowed**: Absolute paths, drive-letter paths (e.g. `C:\...`), `file://`.
- **Resolution**: Paths resolved relative to run root. Rejection is enforced by `tools/validate_fitting_manifest.py --strict-run`.

---

## Reference Files

- `contracts/geometry_manifest.schema.json` — $comment on path policy
- `contracts/GEOMETRY_MANIFEST_PATH_POLICY.md` — Schema vs Consumer scope
- `contracts/fitting_interface_v0.md` — Path Policy, U1 Minimal Artifacts Gate (body)
- This document: `contracts/body_consumer_path_policy_v1.md`
