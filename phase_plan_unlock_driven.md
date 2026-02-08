# Phase Plan (Unlock-driven) — P0~P3

## 0. 원칙
- Phase는 “시간”이 아니라 **언락 달성 상태**로 정의한다.
- 각 Phase의 종료 조건은 **UNLOCK 조건(DoD) 문서**를 참조한다.
- 목표는 **U2 봉인(Freeze + 달성)** 이며, U3는 후속 단계로 연기한다.

---

## P0 — U1 규칙을 “강제 가능(enforceable)” 상태로 만들기
### 목표
U1에서 요구하는 파일명/스키마/게이트/manifest 규칙을 “구현이 강제 가능한 상태”로 정리한다.

### 종료 조건(ALL)
- 공통 `geometry_manifest.json` 규칙이 enforceable:
  - created_at 형식 고정(UTC Z, 밀리초 금지)
  - created_at fingerprint 미포함
  - inputs_fingerprint 결정적 규칙(SHA-256 + canonicalization + 구성요소) 확정
  - version_keys 4종 + UNSPECIFIED+warning 규칙 확정
  - artifacts 경로: run root 기준 상대경로만 허용
- Body → Fitting U1 enforceable:
  - `body_measurements_subset.json` Official Interface Artifact REQUIRED
  - 최소 스키마(unit=m, pose_id=PZ1, 3키, warnings 배열, NaN 금지/null만)
  - 결측 정책(1개 null soft, 2개 이상 degraded/high warning) 확정
- Garment → Fitting U1 enforceable:
  - glb+meta REQUIRED, npz RECOMMENDED(Internal Perf)
  - Hard Gate 정책(플래그 2종) + “meta/manifest 필수 생성, glb/npz 생략 가능” 확정
- Fitting U1 enforceable:
  - 입력 우선순위(npz 우선 → glb+meta fallback) 확정
  - legacy template_params 언급 0회 규칙 확정
  - 산출물 최소 세트(geometry_manifest.json + fitting_facts_summary.json) 확정

---

## P1 — Producer(Body/Garment) U2 준비 완료
### 목표
Body/Garment가 U2 스모크 3종을 구성/지원할 수 있는 상태로 만든다(연동 전 단계).

### 종료 조건(ALL)
- Body는 U1 조건을 충족하며, Smoke-3(1개 null / 2개 이상 null) 입력/출력/경고 등급이 재현 가능하다.
- Garment는 U1 조건을 충족하며, Smoke-2(Hard Gate) 케이스에서 meta/manifest가 항상 생성된다.
- 두 모듈 모두 geometry_manifest 규칙(created_at/fingerprint/version_keys/artifacts path)을 준수한다.

---

## P2 — Fitting U2 봉인(End-to-End Smoke 3종 통과)
### 목표
Freeze된 스모크 3종을 **End-to-End로 통과**시키며 U2를 봉인한다.

### 종료 조건(ALL)
- Fitting은 U1 조건(입력 우선순위/fast-fail/facts+manifest)을 모두 충족한다.
- Smoke-1/2/3 시나리오가 **동일한 정의로** E2E 실행 가능하며, 요구 산출물이 생성된다:
  - Smoke-1: 정상 완료 + facts/manifest 존재
  - Smoke-2: 루프 없이 즉시 종료 + meta/manifest 존재 + facts에 early_exit 기록
  - Smoke-3: null 정책(soft vs degraded/high warning)이 facts/manifest warnings에 반영

---

## P3 — U3(운영/성능) 단계로 이행 (후속)
### 목표
U2 봉인 이후, 운영/성능 관련 규칙을 도입한다(U3 정의/달성).

### 종료 조건(정의만 유지, 상세는 후속 문서)
- 캐시/TTL/재시도/timeout 관측 및 추적(version bump 포함)
- 비용/성능 지표 연결
- garment_proxy.npz 생성/표준화(권장) 및 운영 규칙 연결
