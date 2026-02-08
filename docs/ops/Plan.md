P0 — U1 규칙을 “강제 가능(enforceable)” 상태로 만들기

Phase 종료 조건: U1의 파일명/스키마/게이트/manifest 규칙을 “코드로 강제”할 수 있음

Step 1) 공통: geometry_manifest.v1 강제 레이어 구축

body

해야할 일:

geometry_manifest.json 생성 로직/검증기(validator) 고정: created_at 형식, fingerprint 규칙, version_keys 4종, artifacts 상대경로

언락 조건: U1 공통 manifest 규칙이 enforceable

DoD:

모든 body run output에 geometry_manifest.json 존재

created_at가 fingerprint에 포함되지 않음

version_keys null 금지 + UNSPECIFIED 시 warning 기록

garment

해야할 일: (동일)

언락 조건: (동일)

DoD: (동일)

fitting

해야할 일: (동일)

언락 조건: (동일)

DoD: (동일)

Step 2) Body→Fitting U1 인터페이스 산출물 “고정”

body

해야할 일:

U1 최소 산출물 3종 생성: body_mesh.npz, body_measurements_subset.json, geometry_manifest.json 

unlock_conditions_u1_u2

subset 최소 스키마 고정: unit="m", pose_id="PZ1", keys에 BUST/WAIST/HIP 포함, NaN 금지(null만), warnings 배열

언락 조건: Body→Fitting U1 만족

DoD:

3키 중 1개 null → Soft Warning / 2개 이상 null → Degraded/High Warning이 facts/manifest warnings에 기록 

unlock_conditions_u1_u2

garment

해야할 일: (없음 — Step2는 Body 중심)

언락 조건: -

DoD: -

fitting

해야할 일:

Body subset 입력 파서(3키 + null 정책)만이라도 “죽지 않고” 읽어서 fitting_facts_summary.json에 경고/디그레이드 상태를 반영하는 골격 마련 

unlock_conditions_u1_u2

언락 조건: Fitting U1 산출물 최소세트 생산 가능

DoD:

fitting_facts_summary.json에 warnings_summary, degraded_state가 기록됨 

unlock_conditions_u1_u2

Step 3) Garment→Fitting U1 인터페이스 + Hard Gate 강제

garment

해야할 일:

U1 REQUIRED 산출물: garment_proxy_mesh.glb, garment_proxy_meta.json, geometry_manifest.json

Hard Gate 플래그 2종을 meta에 필수 필드로 기록: negative_face_area_flag, self_intersection_flag

Hard Gate 발생 시에도 meta/manifest는 반드시 생성, glb/npz는 생략 가능 정책 구현 

unlock_conditions_u1_u2

언락 조건: Garment→Fitting U1 만족

DoD:

Hard Gate 케이스에서 “거부 + meta/manifest 생성”이 재현 가능

body

해야할 일: -

언락 조건: -

DoD: -

fitting

해야할 일:

입력 우선순위 강제: garment_proxy.npz 우선, 없으면 glb+meta fallback 

unlock_conditions_u1_u2

Hard Gate 플래그가 true면 루프 없이 즉시 Early Exit 

unlock_conditions_u1_u2

언락 조건: Fitting U1 “fast-fail + facts” 가능

DoD:

fitting_facts_summary.json에 early_exit=true, early_exit_reason 기록 

unlock_conditions_u1_u2

Step 4) “레거시 입력 금지” 문서/검증 동기화

핵심 충돌 포인트: U1 Freeze는 “garment_template_params.json 언급 0회”를 요구합니다. 

unlock_conditions_u1_u2


→ 현재 fitting 문서에는 해당 레거시가 언급/혼재될 위험이 있으므로(P0에서) 문서/검증 규칙을 맞춰야 합니다. 

fitting_module_plan_v1

body

해야할 일: -

언락 조건: -

DoD: -

garment

해야할 일:

Fitting 입력으로는 template_params가 절대 노출되지 않도록(garment 내부용이면 내부로 격리) 정리

언락 조건: U1 “template_params 금지”와 충돌 없음 

unlock_conditions_u1_u2

DoD:

외부로 나가는 계약/산출물에서 template_params 제거(또는 내부용 표시 + Fitting 미사용 보장)

fitting

해야할 일:

입력 계약/파서에서 template_params 경로를 삭제하고, 오직 npz 또는 glb+meta만 허용

언락 조건: U1 enforceable

DoD:

fitting 문서/계약 내 “template_params 류” 언급 0회(정적 검사/CI 룰로도 가능) 

unlock_conditions_u1_u2

P1 — Producer(Body/Garment) U2 준비 완료

Phase 종료 조건: Body는 Smoke-3(Null 정책), Garment는 Smoke-2(Hard Gate) 재현 가능 + 둘 다 manifest 규칙 준수

Step 1) Body: Smoke-3 (subset null) 시나리오 생산/고정

body

해야할 일:

Smoke-3 Case A/B를 “입력/출력/경고 등급”까지 재현 가능한 fixture/러너를 만든다

측정 엔진 관점에서: 최소 K_fit(초기 안정 키셋)를 우선 안정화(폭주/NaN/불연속 방어)

언락 조건: P1 종료 조건 중 Body 파트

DoD:

Case A: 3키 중 정확히 1개 null → Soft Warning

Case B: 3키 중 2개 이상 null → Degraded/High Warning

위 등급이 warnings(또는 warnings_path)와 geometry_manifest.json에 반영 

unlock_conditions_u1_u2

garment

해야할 일: -

언락 조건: -

DoD: -

fitting

해야할 일: (아직 E2E 전, 파서 수준이면 충분)

언락 조건: -

DoD: -

Step 2) Garment: Smoke-2 (Hard Gate) 시나리오 생산/고정

garment

해야할 일:

negative_face_area_flag=true 또는 self_intersection_flag=true인 meta fixture 생성

Hard Gate 케이스에서도 meta/manifest는 항상 생성되도록 보장

언락 조건: P1 종료 조건 중 Garment 파트

DoD:

Hard Gate 케이스에서 glb/npz가 생략되어도 meta/manifest는 존재 

unlock_conditions_u1_u2

body / fitting

해야할 일: -

언락 조건: -

DoD: -

Step 3) Producer 공통: inputs_fingerprint 결정론 재현성 체크

body

해야할 일:

body_measurements_subset.json / body_mesh.npz 해시 포함 규칙 준수(정렬/공백 제거) 

unlock_conditions_u1_u2

언락 조건: U2 준비(“고정된 형태”의 스모크 입력이 흔들리지 않음)

DoD:

동일 입력 → 동일 fingerprint (created_at 제외) 

unlock_conditions_u1_u2

garment

해야할 일:

garment_proxy_meta.json canonical hash + (npz 있으면 npz, 없으면 glb) 해시 규칙 준수 

unlock_conditions_u1_u2

언락 조건: 동일

DoD: 동일

fitting

해야할 일: -

언락 조건: -

DoD: -

P2 — Fitting U2 봉인(End-to-End Smoke 3종 통과)

Phase 종료 조건: Smoke-1/2/3를 동일 정의로 E2E 통과 + 산출물 생성

Step 1) Fitting: U1 입력 계약 준수 + facts/manifest “항상 생성”

fitting

해야할 일:

입력 우선순위(npz 우선 → glb+meta fallback) 구현

산출물 최소세트 “항상 생성”: geometry_manifest.json + fitting_facts_summary.json 

unlock_conditions_u1_u2

언락 조건: Fitting U1

DoD:

실패/early-exit여도 facts/manifest는 남는다(조용한 오답 금지)

body / garment

해야할 일: P1에서 만든 fixture를 Fitting이 읽을 수 있게 전달(artifact-only)

언락 조건: -

DoD: -

Step 2) Smoke-1 정상 E2E

body

해야할 일: 정상 케이스 산출물(3종) 제공 

unlock_conditions_u1_u2

언락 조건: U2 Smoke-1 

unlock_conditions_u1_u2

DoD: manifest + subset + mesh 존재

garment

해야할 일: 정상 케이스 산출물(glb+meta(+npz)) 제공

언락 조건: U2 Smoke-1

DoD: manifest + meta + glb(및 선택 npz)

fitting

해야할 일: 정상 종료 + facts/manifest 생성 

unlock_conditions_u1_u2

언락 조건: U2 Smoke-1 

unlock_conditions_u1_u2

DoD:

early_exit=false

garment_input_path_used가 실제 경로(npz/glb_fallback)와 일치 

unlock_conditions_u1_u2

Step 3) Smoke-2 Garment Hard Gate E2E (Early Exit)

garment

해야할 일: Hard Gate fixture 제공(meta/manifest 필수)

언락 조건: U2 Smoke-2 

unlock_conditions_u1_u2

DoD: meta/manifest 존재

fitting

해야할 일: 루프 없이 즉시 종료(Early Exit)

언락 조건: U2 Smoke-2 

unlock_conditions_u1_u2

DoD:

early_exit=true

early_exit_reason 기록

facts/manifest 존재 

unlock_conditions_u1_u2

body

해야할 일: (정상 body여도 됨)

언락 조건: -

DoD: -

Step 4) Smoke-3 Body subset null E2E (Soft vs Degraded)

body

해야할 일: Case A/B fixture 제공

언락 조건: U2 Smoke-3 

unlock_conditions_u1_u2

DoD: subset/manifest에 등급 신호 반영

fitting

해야할 일: warning/degraded 등급을 facts/manifest에 “재기록” (downstream에서도 관측 가능하게)

언락 조건: U2 Smoke-3 

unlock_conditions_u1_u2

DoD:

Case A → degraded_state="none" + warnings_summary에 soft

Case B → degraded_state="high_warning_degraded" + warnings_summary에 high 

unlock_conditions_u1_u2

garment

해야할 일: (정상 garment여도 됨)

언락 조건: -

DoD: -

P3 — U3(운영/성능) 단계로 이행 (후속)

Phase 종료 조건(개요): U2 봉인 이후 운영/성능 규칙 도입(캐시/텔레메트리/재시도/비용) + 고급 기능 확장

Step 1) Body 운영 고도화 (B3~B4)

body

해야할 일:

Online inference 완성(입력→prototype 선택→β 로드→mesh 생성→subset 산출) + 예산 준수 

Body_Module_Plan_v1

캐시/2cm quant + 텔레메트리(hit/miss, latency, VRAM)

언락 조건: U3(운영/성능) 진입 조건(내부) 

phase_plan_unlock_driven

DoD:

p95 latency/VRAM 예산 관측 가능

캐시 무효화(version key 변화) 동작 

Body_Module_Plan_v1

garment / fitting

해야할 일: -

언락 조건: -

DoD: -

Step 2) Garment 오프라인 파이프라인 확장 (G0~G5 안정화)

garment

해야할 일:

G1.5 Swatch gatekeeper(이물질 탐지 포함) 결과 기록 체계 고정 

garment_Product Contract v0.9-r…

G2 템플릿 프록시 + warp metrics + distortion gate 운영 

garment_Product Contract v0.9-r…

G4 Texture DNA(offline latent) 생성/재가공 플래그(needs_reprocessing) 운영 

garment_Product Contract v0.9-r…

G5 material_token→thickness 기본값 정책 + warning 기록

언락 조건: U3 운영 정책으로 승격(오프라인 배치/보관/재가공)

DoD:

Hard/Soft gate가 “조용히 통과”하지 않고 항상 provenance/warnings로 남음 

garment_Product Contract v0.9-r…

body / fitting

해야할 일: -

언락 조건: -

DoD: -

Step 3) Fitting 고급 기능 완성 (F3~F7)

fitting

해야할 일:

Tier-0 SDF bank 생성 + warm cache/텔레메트리 

fitting_module_plan_v1

Tier-1 constraint solver + penalty/score + 노출 게이트(score<70 degrade) 

fitting_module_plan_v1

condition images(depth/normal) + fixed_camera_preset_v1 정합

Sensors + regeneration loop(재시도 2, timeout 3s, iter limit 100, memory clear, falloff inflate) 

fitting_module_plan_v1

Retention(Hot Logs 30d + Summary 장기) 적용

언락 조건: U3 운영/성능 달성(내부 정의) 

phase_plan_unlock_driven

DoD:

예산 상한(지연/VRAM/재시도)이 관측·강제 가능

실패/재시도 히스토리가 retention 정책에 따라 보관

body / garment

해야할 일: Fitting의 ROI/로고 보호 입력(logo_anchor 등) 제공/정합

언락 조건: -

DoD: -

Step 4) Ops/검증 루프 정착(라운드/레지스트리/KPI_DIFF)

body / garment / fitting

해야할 일:

“라운드 마감(postprocess) → KPI/KPI_DIFF/LINEAGE 갱신”을 표준화된 진입점으로 고정 

INDEX

로컬 산출물 커밋 금지(verification/runs/**), facts-only 누적(coverage_backlog 등) 

INDEX

언락 조건: U3 운영 체계 정착(내부)

DoD:

베이스라인/prev 추론 규칙이 깨지지 않고 회귀 추적 가능 

INDEX