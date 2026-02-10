# Unit Standard (Canonical Units)

## Scope
This document defines canonical measurement units used across the project.
It is a **Contract-layer** rule and applies to all measurement keys and datasets unless explicitly stated otherwise.

## Canonical Unit
- **All measurement values in this project are canonicalized to meters (m).**
- Standard keys that represent measurements MUST use a suffix that indicates unit when appropriate (e.g., `*_CIRC_M`).

## Precision Policy
### Canonical (storage/interchange)
- Canonical values SHOULD be represented in meters with **millimeter resolution**.
- Canonical precision target: **0.001 m (1 mm)**.

### Display / Reporting
- Any value presented in docs, logs, reports, UI, or exported artifacts SHOULD be quantized to:
  - **0.001 m (round half-up)**
- This ensures stable diffs and consistent comparisons across runs.

## Ingestion Rule (Raw → Canonical)
- Raw data may exist in mm/cm/m formats, but MUST be preserved in original units during raw storage.
- Processed/canonical data MUST be in meters (m). External display/contract interfaces MUST use meters.
- If upstream/raw data is in cm, it MUST be converted during ingestion:
  - `meters = cm / 100`
- If upstream/raw data is already in meters, it MUST be validated as meters.
- Ingestion MUST record provenance (at minimum):
  - source unit (e.g., `cm` or `m`)
  - conversion applied (e.g., `cm_to_m`)
  - quantization policy used for reporting (e.g., `0.001m`)

## Non-goals
- This document does not define validation pass/fail logic.
- This document does not mandate a database schema change.
