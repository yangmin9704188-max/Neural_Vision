# Geometry Manifest Path Policy

**Scope**: Clarifies schema vs consumer policy for artifact paths. Facts-only.

---

## Schema Scope vs Consumer Policy Scope

- **geometry_manifest.schema.json**: Defines payload shape (required fields, types). Path fields are string; schema does not enforce absolute vs relative.
- **Consumer policy**: The module or pipeline that consumes geometry_manifest may impose stricter rules. Consumer policy overrides schema allowance when enforced.

---

## fitting strict-run Override (Example)

- **fitting_interface_v0.md** Path Policy: Run-root-relative only. Absolute paths, drive-letter paths (e.g. `C:\...`), and `file://` are rejected.
- **strict-run validator** (`tools/validate_fitting_manifest.py --strict-run`): Enforces run-root-relative for all artifact paths in body/garment geometry manifests.
- When fitting strict-run is used, geometry_manifest artifacts paths must be run-root-relative; absolute paths cause FAIL.

---

## Where to Look

- **Schema**: `contracts/geometry_manifest.schema.json` — payload shape, $comment on path policy.
- **Fitting consumer policy**: `contracts/fitting_interface_v0.md` — Path Policy section, U1 Minimal Artifacts Gate.
- **Body consumer path policy**: `contracts/body_consumer_path_policy_v1.md` — run-root-relative when fitting consumes body geometry_manifest.
- **Garment consumer path policy**: `contracts/garment_consumer_path_policy_v1.md` — run-root-relative when fitting consumes garment geometry_manifest.
- **Other modules**: Each module's contract (body, garment, fitting) may declare its own path policy. The module contract for the consumer takes precedence.
