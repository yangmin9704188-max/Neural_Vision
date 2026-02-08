# Body Subset Key Mapping — Contract (v1)

**Purpose**: Deterministic normalization of body subset input keys to canonical standard keys. Facts-only; no quality pass/fail thresholds.

**Contract anchor**: `contracts/fitting_interface_v0.md` Key Space section.

---

## Canonical Standard Keys (v1 Scope)

| Canonical Key | Description |
|---------------|-------------|
| `BUST_CIRC_M` | Bust circumference (meters) |
| `WAIST_CIRC_M` | Waist circumference (meters) |
| `HIP_CIRC_M` | Hip circumference (meters) |

---

## Alias Key Normalization Rules

### Case and Separator

- **Case-insensitive**: All key matching is case-insensitive (e.g. `Bust`, `BUST`, `bust` are equivalent).
- **Separator normalization**: Characters `" "`, `"-"`, `"_"` are treated as equivalent and normalized to `"_"` before lookup (e.g. `bust-circ`, `bust_circ`, `bust circ` → `bust_circ`).

### Allowed Variants

- Prefix/suffix variants allowed: `bust`, `bust_circ`, `chest_circumference`, `bust_circumference_m`, etc.
- Exact mapping defined in `labs/specs/body_subset_keymap.v1.json`.

---

## Deterministic Tie-Break

When multiple source keys map to the same canonical key:

- **Priority**: Use the alias order in the keymap. The first matching alias in the keymap's alias list for that canonical wins.
- **Source order**: If multiple source keys match the same alias (after normalization), the first source key encountered (deterministic iteration order) wins.
- This choice is recorded in the mapping output.

---

## Recording Rules

### keymap_applied (Recommended Field)

- When producing normalized output or fitting_facts_summary, record the applied mapping as an array of `{ src, dst, status }` entries.
- `status`: `"mapped"` | `"unmapped"` | `"tie_broken"`.
- If the schema disallows new top-level fields (e.g. fitting_facts_summary.v1 `additionalProperties: false`), store inside `degraded_state` as `keymap_applied` or `mapping_summary`.

### Mapping Failure / Unmapped Keys

- **Code**: `BODY_SUBSET_UNMAPPED_KEY` — source key could not be mapped to any canonical.
- **Code**: `BODY_SUBSET_MISSING_CANONICAL_KEYS` — one or more canonical keys have no value (null) after mapping.
- Record in `degraded_state` and `warnings_summary` per existing fitting_facts_summary contract.

---

## NaN/Infinity Handling

- Input values that are NaN or Infinity must be serialized as `null` in JSON.
- Document in schema: discovery of NaN/Infinity in input triggers null handling; no crash.
