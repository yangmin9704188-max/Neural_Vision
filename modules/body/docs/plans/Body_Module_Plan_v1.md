Body Module Plan v1 (B2B 운영용)
0. Document Header

Module: Body

Owner: 민영

Version: v1.0

Last Updated: 2026-01-30

Product Scope: MVP = Shirt-only, PZ1(A-pose) 고정

Runtime Mode: Hybrid (Offline precompute + Online inference)

1. Mission

제한 입력(키/몸무게/성별/나이 + 일부 옵션)만으로 한국인 특화 3D Body Mesh를 저비용/재현 가능하게 생성한다. (PZ1 고정)

2. Product Goals (정량 포함)
2.1 Quality Goals

결정성/재현성: 동일 입력 + 동일 버전 키 → 동일 출력

측정치 정합성(초기 범위): 토르소 5(가슴/밑가슴/허리/엉덩이/어깨) + 목

목표: 부위별 1cm 이내

운영: hard PASS/FAIL이 아니라 품질 점수 + 노출 게이트로 관리(7-B2/8 참고)

Pose 고정: PZ1(A-pose)에서만 측정/캘리브레이션 수행

2.2 Compute Budget (TBD 금지: 최대 허용치 명시)
(A) Pipeline-level Budget (환경 프로파일)

Local Dev Profile (4070 Super, 12GB): Pipeline Peak VRAM <= 12GB

Cloud Production Profile: GPU class별 Pipeline Peak VRAM 상한 별도 정의(예: 24GB/40GB 등)

(B) Module-level Budget (Body 몫)

Online budget (per request, Body 단계)

p95 latency: <= 2.0s

Peak VRAM (Body 전용): <= 6GB (권장 4~6GB)

GPU compute time (Body 전용): <= 0.5s / request

CPU compute time (Body 전용): <= 0.7s / request

Output payload size

internal npz(mesh): <= 8MB

internal subset json: <= 64KB

Offline budget

캘리브레이션 시간 상한: <= 5분 / prototype

프로토타입 파라미터 파일(prototype_params/*.npz): <= 2MB / prototype (상한)

(선택) 월간 재가공 GPU-hours 상한: 운영에서 설정(초기값은 프로젝트 운영자가 지정)

예산 초과 정책(필수)

Online: 캐시 우선, 파생 산출(glb export 등) 비활성화/지연 처리

Offline: 5분 초과 시 중단 → 근사 β 저장 가능하나 품질 점수/노출 게이트로 차단(7-B2)

3. Non-Goals

Online 최적화 루프(0)

45키 전체 맞추기(초기: 토르소5+목)

포즈 다양화/포즈별 캘리브레이션(PZ1 고정)

Garment/Fitting 구현

SizeKorea 의미론 검증

4. Inputs
4.1 Online Inputs (user_body_request)

Required: sex, age, height_cm, weight_kg

Optional: shoulder_drag_cm, waist_in, female_cup_size (예: 75A, 80B)

4.1.1 Unit Policy (내부 정규화)

입력 단위:

height: cm, shoulder: cm, waist: inch, weight: kg, cup: canonical string

내부 단위:

길이/둘레: m, 무게: kg

4.1.2 Centralized Unit Converter Rule (운영 규칙)

모든 단위 변환은 core/utils/unit_converter.py에서만 수행한다.

코드 어디에서도 /100, *0.0254 같은 매직 넘버로 변환하지 않는다.

이를 위반한 코드는 코드 리뷰에서 반려한다.

4.1.3 Gate Policy

Hard Gate (즉시 거절)

필수 4종 중 null/비숫자 존재

height_cm < 100 또는 height_cm > 220

Soft Gate

옵션 파싱 실패/범위 실패 → 무시하고 진행 + OPTION_OUT_OF_RANGE 또는 OPTION_PARSE_FAILED 경고

5. Interface Contract (Output / Asset)
5.1 Coordinate System & Precision (고정)

Origin: 양발 사이 바닥 정중앙 (0,0,0)

Axis: Y-up, Z-forward

Unit: meters(m), weight kg

dtype:

Internal 저장/측정 계산: float32

Online export/전송: float16 허용

단, subset 측정치는 float32로 upcast해 계산

5.2 Prototype Bank Artifacts

prototype_index.json, prototype_meta.json, prototype_targets.json, prototype_params/{id}.npz

body_measurements_subset.json (internal artifact)

5.3 Mesh Output Formats (이원화)

Internal (기본): body_mesh.npz

목적: 빠른 로드/저장, 내부 파이프라인, 캐시 효율

External (협력사/프론트 통합용 선택 제공): body_mesh.glb

목적: Blender/Unreal/Three.js 등 외부 통합 가속

정책: 기본 응답은 npz 유지. 외부 통합이 필요한 계약/API에서만 glb export를 켠다.

glb는 “파생 산출물”이며, 비용/지연이 예산을 초과하면 비활성화 가능(2.2 정책 준수)

6. Assets & Storage Lifecycle

Prototype Bank: warm, 버전 축적(무기한)

Online Cache: hot, TTL+LRU, 버전 변경 시 무효화

7. Milestones
B0. curated_v0 공급 안정

DoD: m/kg 정규화, 핵심 컬럼 확보, warnings/completeness 생성

B1. Prototype Bank 생성

bin schema: sex(2) × height_q(8) × BMI_q(6) × age_bucket(4)

Age Buckets (생애 주기별 4구간 고정)

[10,14], [15,29], [30,49], [50,∞)

merge: age → BMI → height

대표: P1(메도이드)

B1 확장 계획(미래-proof)

MVP는 위 Age_Bins 유지(384-bin 예산 고정).

바지/하체(Hip/Thigh) 등 확장 시, [15,29]는 아래로 분할하는 확장안을 적용한다:

[15,19], [20,29]

이 변경은 binning_version major bump로 취급한다(9 참고).

B2. Offline β 캘리브레이션(프로토타입당 1회)

목표: 토르소5+목 1cm 목표

시간 상한: <= 5분 / prototype

B2 운영 안전장치: Quality Score + 노출 게이트

calibration_quality_score (0~100)를 저장/기록한다.

노출 게이트:

calibration_quality_score < 70 → 서비스 노출 금지(차단) 또는 degrade 경로 강제

“근사 β”는 경고만 남기지 않고 score로 격리/차단한다.

권장 score 구성(가중치 + 스무딩 안정성)

측정 오차 기반(부위 가중치):

Error는 cm로 통일, 가슴/허리 가중치를 더 높게

추가 항(권장, 10% 내외): 메쉬 안정성 지표(Spike 방어)

예: curvature stability / Laplacian residual 등 “수치화 가능한 지표”만 포함

최종 형태(예시):

score = 0.9 * score_measurement + 0.1 * score_smoothness

각 score 정의/스케일은 calibration_version에 귀속(버전관리)

B3. Online Inference

입력→prototype 선택→β 로드→mesh 생성→subset 산출

예산 준수: p95 2.0s, GPU 0.5s, VRAM 6GB

B4. 캐시/2cm quant + 텔레메트리

cache key: (prototype_id, height_quant_2cm, pose_id)

hit/miss, latency, VRAM 기록

8. Quality Gates & Telemetry

Hard:

필수 입력 실패, height 범위 실패

mesh 생성 치명 실패

calibration_quality_score < 70 자산 노출 금지

Soft:

옵션 실패 경고

subset 결측 경고

Telemetry:

online: p50/p95 latency, peak VRAM(Body), gpu_time(Body), cache hit rate

offline: prototype별 캘리브레이션 시간/score 분포/오차 분포, 스무딩 지표 분포

9. Versioning & Cache Invalidation
9.1 Version Keys

dataset_version

binning_version (Age_Bins 포함)

selection_version

smplx_model_version

calibration_version

measurement_tool_version

pose_id

9.2 Cache Invalidation

아래 변경 시 관련 캐시는 즉시 무효화:

binning_version, selection_version

smplx_model_version, calibration_version

measurement_tool_version

pose_id

Prototype Bank 재생성 트리거(major):

dataset major, binning major(예: Age_Bins 분할), smplx major, calibration major

10. Deterministic Selection & Tie-breaker

입력을 내부 단위로 정규화(m/kg)

height는 2cm quant

경계/동률이면 무조건 upper bin 선택

옵션 유효 시 Top-K를 score로 재정렬

10.1 경계값 안정성 규칙(부동소수점 방어)

경계값 비교는 float 비교 금지.

반올림/정수화 후 비교를 강제한다.

예: height_cm는 정수 cm로 정규화 후 quant 적용, 그 결과로 bin 결정을 수행