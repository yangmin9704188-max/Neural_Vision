# U1/U2 DoD 체크리스트 v0 (Smoke 중심)

원칙:
- 추론 금지.
- U1/U2 문서에 명시된 산출물 존재/스키마/게이트/스모크 케이스만 체크한다.
- 케이스별로 "필수 산출물 존재 + 게이트 판정 + warnings/facts"가 어떻게 나와야 하는지를 확인한다.

---

## A) 공통 체크(모든 시나리오 공통)

### A.1 geometry_manifest.json 존재
- [ ] run output 디렉토리에 geometry_manifest.json 존재

### A.2 geometry_manifest.json 최소 스펙
- [ ] created_at == "YYYY-MM-DDTHH:MM:SSZ" (UTC Z, 밀리초 없음)
- [ ] inputs_fingerprint 존재 (SHA-256 기반)
- [ ] version_keys 4종 null 아님
  - [ ] snapshot_version
  - [ ] semantic_version
  - [ ] geometry_impl_version
  - [ ] dataset_version
  - [ ] 미지정 시 "UNSPECIFIED" + warnings에 VERSION_KEY_UNSPECIFIED:<key>
- [ ] artifacts.*.path는 run root 기준 상대경로(절대경로 없음)

---

## B) U1: Interface Unlock (Body/Garment/Fitting)

### B.1 (U1-Body) Body → Fitting 산출물
- [ ] body_mesh.npz 존재
- [ ] body_measurements_subset.json 존재 (Official Interface Artifact)
- [ ] body_measurements_subset.json 최소 스키마
  - [ ] unit == "m"
  - [ ] pose_id == "PZ1"
  - [ ] keys에 BUST_CIRC_M, WAIST_CIRC_M, HIP_CIRC_M 포함
  - [ ] 결측은 null만 허용, NaN 없음
  - [ ] warnings 배열 존재 (empty 허용)

### B.2 (U1-Garment) Garment → Fitting 산출물
- [ ] REQUIRED
  - [ ] garment_proxy_mesh.glb 존재
  - [ ] garment_proxy_meta.json 존재
  - [ ] geometry_manifest.json 존재
- [ ] RECOMMENDED
  - [ ] garment_proxy.npz 존재 시 Fitting 우선 사용
  - [ ] garment_proxy.npz 없으면 glb+meta fallback

### B.3 (U1-Fitting) Fitting 산출물/입력 우선순위
- [ ] 입력 우선순위 준수
  - [ ] garment_proxy.npz 있으면 사용
  - [ ] 없으면 garment_proxy_mesh.glb + garment_proxy_meta.json fallback
- [ ] template_params 류(legacy) 언급/사용 0회(U1/U2 범위)
- [ ] REQUIRED 산출물
  - [ ] geometry_manifest.json
  - [ ] fitting_facts_summary.json
- [ ] fitting_facts_summary.json 최소 필드
  - [ ] garment_input_path_used ∈ {"npz","glb_fallback"}
  - [ ] early_exit: boolean
  - [ ] early_exit_reason: string|null
  - [ ] warnings_summary: array(또는 구조)
  - [ ] degraded_state ∈ {"none","high_warning_degraded"}

---

## C) U2: Runnable Unlock (Smoke 3종 고정)

### C.1 Smoke-1 정상(E2E 성공)
- [ ] geometry_manifest.json 존재
- [ ] fitting_facts_summary.json 존재

### C.2 Smoke-2 Garment Hard Gate(Early Exit)
- [ ] garment_proxy_meta.json 플래그
  - [ ] negative_face_area_flag == true OR self_intersection_flag == true
- [ ] Garment Hard Gate 시에도 반드시 생성(추적성)
  - [ ] garment_proxy_meta.json
  - [ ] geometry_manifest.json
- [ ] Fitting: 루프 없이 즉시 종료(Early Exit)
- [ ] fitting_facts_summary.json에 early_exit 신호 기록

### C.3 Smoke-3 Body subset null (Soft vs Degraded)
- Case A (Soft)
  - [ ] 3키 중 1개 null → Soft Warning
- Case B (Degraded)
  - [ ] 3키 중 2개 이상 null → Degraded / High Warning
- [ ] warning/degraded 등급이 facts/manifest warnings에 반영

---

## D) 추론 없이 해결해야 하는 질문(문서 충돌/공백)

1) Fitting 산출물 이름 충돌
- U1/U2는 fitting_facts_summary.json(필수)을 요구
- fitting_interface_v0는 facts_summary.json / fitting_summary.json를 정의
- 정본 선택 필요:
  - (A) fitting_facts_summary.json로 단일화
  - (B) facts_summary.json로 통일
  - (C) 둘 다 생성(역할 분리)

2) KPI/KPI_DIFF 저장 위치/파일명(파일명/위치만 확정됨)
- exports/runs/<lane>/<run_id>/KPI.json
- exports/runs/<lane>/<run_id>/KPI_DIFF.md

3) Garment 입력 계약 충돌
- U1/U2는 proxy(glb/meta/npz) 중심
- fitting_module_plan에는 template_params 언급 존재
- U1/U2 범위에서 fitting_module_plan의 위치(갱신/이관) 확정 필요

---