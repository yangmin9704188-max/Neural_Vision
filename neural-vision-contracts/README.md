# neural-vision-contracts

Public artifact contracts for the Neural Vision virtual fitting pipeline.

## What This Repo Contains

| Directory | Purpose |
|-----------|---------|
| `schemas/` | JSON Schema (2020-12) definitions for all public interface artifacts |
| `measurement/` | Measurement key dictionary and unit standard |
| `datasets/` | Dataset format contracts (NPZ, etc.) |
| `catalog/` | Gate / warning / error code catalog |
| `openapi/` | OpenAPI 3.1 specification + bundled dist |
| `examples/` | Smoke-test request/response examples (schema-validated) |

## Quick Start

```bash
# Validate all examples against schemas
python scripts/validate_examples.py

# Bundle OpenAPI (requires redocly or swagger-cli)
npx @redocly/cli bundle openapi/neural-vision-api.v1.yaml -o openapi/dist/neural-vision-api.v1.bundle.yaml
```

## Versioning (Semver)

This repo follows **Semantic Versioning 2.0.0** with the following contract-specific rules:

| Change Type | Bump | Example |
|-------------|------|---------|
| Add optional field to a schema | PATCH | New `notes` field with `additionalProperties: true` |
| Promote optional field to required (producers only) | MINOR | `warnings_path` becomes required |
| Remove/rename required field, change type | MAJOR | `inputs_fingerprint` type change |
| Any change that makes a previously valid JSON **invalid** | **MAJOR** | Tightening `pattern`, removing `enum` value |

### Backward Compatibility Rule

> **If a JSON document that was valid under version N becomes invalid under version N+1,
> that is a MAJOR (breaking) change — no exceptions.**

### U1/U2 Freeze

Schemas tagged with "U1 Freeze" in their title are **frozen**.
Changes to frozen schemas require a formal unlock review and are forbidden
under normal development.

## Pinning (for consumers)

Engine, Demo, and Lab repos pin a specific tag of this contracts repo:

```jsonc
// contracts_pin.json (placed in consumer repo root)
{
  "contracts_repo": "neural-vision-contracts",
  "pinned_tag": "v0.1.0",
  "pinned_sha": "<commit-sha>"
}
```

Consumer CI checks that local schema copies match the pinned tag.
See `scripts/check_drift.py` for reference implementation.

## License

Proprietary — Neural Vision Project.
