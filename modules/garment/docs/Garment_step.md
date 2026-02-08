Garment 모듈 1인 개발 Step 플랜 (모듈 의존 언락 포함)
## Step 0) “U1 공통 규칙”을 Garment 쪽에서 바로 적용 가능한 형태로 고정

Garment에서 하는 일

geometry_manifest.json 생성 규칙을 그대로 구현/적용(특히: created_at 형식, fingerprint 제외, 상대경로 artifacts, version_keys UNSPECIFIED 규칙).

inputs_fingerprint에 Garment 입력 신호(meta hash + npz 또는 glb hash)를 포함시키는 규칙 반영. 

phase_plan_unlock_driven

언락(다른 모듈 완료 필요)

없음(독립). 공통 규칙은 Freeze라 그대로 따르면 됨.

## Step 1) Garment → Fitting U1 “외부 계약 산출물” 최소 세트 만들기

Garment에서 하는 일

U1 REQUIRED 3종을 항상 생성:

garment_proxy_mesh.glb

garment_proxy_meta.json

geometry_manifest.json

garment_proxy_meta.json에 Contract 필수 필드(왜곡/warp/flag 구조) 포함.

언락(다른 모듈 완료 필요)

Fitting U1 enforceable: 입력 우선순위(npz 우선 → glb+meta fallback)와 fitting_facts_summary.json 최소 필드가 “정의만이라도” 확정돼 있어야, Garment 산출물을 실제로 소비 가능.
(P0 종료 조건에 이미 포함된 항목)

## Step 2) Hard Gate 플래그 2종을 “결정론적으로” 산출하고, Hard Gate 시 규칙 준수

Garment에서 하는 일

garment_proxy_meta.json에 아래 플래그를 반드시 산출:

self_intersection_flag

negative_face_area_flag

Hard Gate 조건(true 발생)일 때 규칙:

garment_proxy_meta.json + geometry_manifest.json은 반드시 생성

garment_proxy_mesh.glb/garment_proxy.npz는 생략 가능

언락(다른 모듈 완료 필요)

Fitting U1 enforceable 중 “Hard Fail(Early Exit) 규칙”이 구현돼 있어야 E2E에서 루프 없이 종료 가능.

## Step 3) U2 Smoke-2(garment hard gate) “재현 가능한 fixture/run” 만들기

Garment에서 하는 일

Smoke-2 케이스를 항상 만들어낼 수 있게:

입력/템플릿 중 하나를 고정해 negative_face_area_flag=true 또는 self_intersection_flag=true가 항상 발생하는 테스트 러너/데이터(= fixture) 구성

Smoke-2에서도 meta/manifest “항상 생성” 보장.

언락(다른 모듈 완료 필요)

Fitting U2(End-to-End Smoke 3종 통과) 를 위한 전제:

Fitting이 Smoke-2에서 “루프 없이 즉시 종료 + facts에 early_exit 기록”을 구현 완료해야 함.

Body 모듈은 이 Step의 직접 의존 없음(Smoke-2는 Garment hard gate 중심).

## Step 4) (권장) garment_proxy.npz 추가 + Fitting “입력 우선순위” 검증

Garment에서 하는 일

garment_proxy.npz를 생성(성능/내부 최적화 목적, U1에서는 RECOMMENDED).

동일 케이스에서 glb+meta fallback과 결과가 크게 어긋나지 않도록 최소 검증(결정론/경로 기록).

언락(다른 모듈 완료 필요)

Fitting U1의 입력 우선순위 구현 완료:

npz 존재 시 우선 사용

없으면 glb+meta fallback

facts에 "garment_input_path_used": "npz"|"glb_fallback" 기록

## Step 5) (U2 이후로 미뤄도 됨) Material/Thickness 최소 정책 산출

Garment에서 하는 일

material_token → stretch_class, thickness_garment_m 산출 + 기본값 정책(THICKNESS_DEFAULTED 경고). 

garment_Product Contract v0.9-r…

(선택) weight_class로 thickness 스케일. 

garment_Product Contract v0.9-r…

언락(다른 모듈 완료 필요)

Fitting 쪽에서 thickness/stetch를 실제로 사용하기 시작한 시점(= U3 성격)에 맞춰야 재작업이 줄어듦.

U1/U2 Freeze 문서에는 thickness가 핵심 언락 조건은 아님(= 당장 U2 봉인 목표면 Step 5는 후순위 가능).

## Step 6) (후속) G1.5 Swatch Gatekeeper + G4 Texture DNA Offline

Garment에서 하는 일

swatch 품질지표 + 이물질 감지 결과 기록(계약상 기록 필수) 

garment_Product Contract v0.9-r…

garment_latent_asset/ + latent_meta.json + needs_reprocessing 운영 

garment_Product Contract v0.9-r…

언락(다른 모듈 완료 필요)

Fitting이 IP-Adapter/latent를 실제 소비하는 운영 단계(U3)에 맞춰 진행하는 편이 안전(지금 U2 봉인 목표엔 비핵심).

한 줄 요약(1인 개발 최단 경로)

**U2 봉인 목표(가장 중요)**만 보면 Garment는 Step 0 → 1 → 2 → 3이 “필수 최소 루트”입니다.

Step 4는 성능/안정성 측면에서 권장, Step 5~6은 U3 성격이라 후순위로 미루는 게 1인 템포에 맞습니다.