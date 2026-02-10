# Changelog

All notable changes to `neural-vision-contracts` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning Rule (Contract-Specific)

> **If a JSON document that was valid under version N becomes invalid under version N+1,
> that is a MAJOR (breaking) change — no exceptions.**

---

## [0.1.0] — 2026-02-10

### Added
- **Schemas (7 public artifacts)**
  - `geometry_manifest.v1.schema.json` — common run manifest (U1 Freeze)
  - `body_measurements_subset.v1.schema.json` — Body→Fitting interface (U1 Freeze)
  - `garment_proxy_meta.v1.schema.json` — Garment hard gate flags (U1 Freeze)
  - `fitting_facts_summary.v1.schema.json` — Fitting output facts (U1 Freeze)
  - `generation_delivery.v1.schema.json` — Generation delivery contract
  - `gen_provenance.v1.schema.json` — Generation provenance tracking
  - `m1_signal.v1.schema.json` — M1 milestone signal
- **Schemas (3 new request schemas)**
  - `body_infer_request.v1.schema.json` — Body inference API request
  - `seller_intake_request.v1.schema.json` — Seller garment intake API request
  - `fitting_run_request.v1.schema.json` — Fitting run API request
- **Documents**
  - `measurement/standard_keys_v0.md` — measurement key dictionary
  - `measurement/unit_standard_v0.md` — canonical unit rules
  - `datasets/npz_contract_v0.md` — NPZ dataset format contract
  - `catalog/errors.md` — gate/warning/error code catalog
- **OpenAPI**
  - `openapi/neural-vision-api.v1.yaml` — OpenAPI 3.1 specification
  - Endpoints: seller/intake, body/infer, fitting/run, generation/run, runs/{id}/manifest, runs/{id}/status
  - Envelope pattern: `{ gate, warnings, manifest, data }`
- **Examples**
  - `examples/smoke1_ok/` — normal E2E success scenario
  - `examples/smoke2_hard_gate/` — garment hard gate early exit
  - `examples/smoke3_degraded/` — body measurement null → degraded state
- **CI**
  - JSON Schema validation of all examples
  - OpenAPI bundle generation
  - `scripts/validate_examples.py` — schema validation runner
