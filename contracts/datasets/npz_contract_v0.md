# NPZ Contract (Golden Dataset Schema)

## Scope
This document defines the contract for NPZ files used as golden datasets in verification and facts-only runners.

## Keys
- `verts`: Required. Vertex coordinates array.
- `case_id`: Optional. Case identifier array. If present, length must match `verts` count or warnings recorded (no exceptions).

## Verts Format
Verts array MUST support one of the following formats:
1. `(N, V, 3)` float array: batched format with N cases, each with V vertices.
2. `(N,) dtype=object` where each element is `(V, 3)` ndarray: object array format.

## Case ID Handling
- If `case_id` length mismatches `verts` count, record in `load_warnings` (no exceptions).
- If `case_id` is missing, generate default IDs (e.g., `case_0000`, `case_0001`, ...).

## Unit Expectation
- Verts coordinates SHOULD be in meters (m) as per `docs/contract/UNIT_STANDARD.md`.
- Unit/scale suspicion (e.g., cm-like values) MUST be recorded as warnings (`UNIT_FAIL`, `PERIMETER_LARGE`) only, not as exceptions or PASS/FAIL judgments.

## Non-goals
- This contract does not define validation pass/fail logic (Validation layer principle).
