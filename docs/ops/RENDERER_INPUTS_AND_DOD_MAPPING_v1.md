# Renderer Inputs and DoD Mapping v1

**목적**: u1_u2_dod_checklist 항목이 master_plan의 plan_items/unlocks로 어떻게 대표되는지 명시한다.  
**원칙**: PASS 근거는 `artifact_observed` + m0/m1_checks로 통일한다.

---

## u1_u2_dod_checklist ↔ master_plan 매핑

| DoD 체크리스트 항목 | master_plan 대표 | artifact_id / plan_id |
|---------------------|------------------|------------------------|
| A.1 geometry_manifest.json 존재 | plan_items (run_minset) | geometry_manifest_root |
| A.2 geometry_manifest 최소 스펙 | M1 checks (dependency_ledger) | (m1_checks) |
| B.1 U1-Body body_measurements_subset | P0.body.emit_subset_m0 | body_subset_m0 |
| B.2 U1-Garment garment_proxy_meta | P0.garment.emit_proxy_meta_m0 | garment_proxy_meta_m0 |
| B.3 U1-Fitting 입력 우선순위 | P0.fitting.u1_ready | (body_subset_m0 + garment_proxy_meta_m0) |
| C.1 Smoke-1 정상 | unlocks U1.FITTING_READY | artifact_observed |
| C.2 Smoke-2 Garment Hard Gate | (gate 로직, 별도) | garment_proxy_meta_m0 플래그 |
| C.3 Smoke-3 Body subset null | (m1 no_nan) | body_subset_m1_nan |

---

## PASS 근거 통일 선언

- **Smoke PASS**는 `master_plan`의 `done_when` / `unlocks` 논리로만 판정한다.
- **artifact_observed**: `path_glob_any`로 `exports/runs/**` 내 파일 매칭 시 true.
- **m0/m1_checks**: dependency_ledger의 require_fields, schema_version, no_nan 등.
- 별도 임의 규칙 금지.

---

## 참조

- `contracts/renderer_input_contract_v1.md`: 렌더러 입력 정본
- `ssot/u1_u2_dod_checklist_v0.md`: DoD 체크리스트
- `contracts/master_plan_v1.json`: SSoT
