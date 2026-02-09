0. Document Header

Module: Fitting

Owner: 민영

Version: v1.0

Last Updated: 2026-01-30 (Asia/Seoul)

Product Scope: Shirt MVP, Body(PZ1) 기반, ControlNet/IP-Adapter 연동

Runtime Mode: Hybrid (Offline SDF Bank + Online Delta + Quality Sensors + Regeneration Loop)

Design Principle: 조용한 오답 금지 + 비용 상한 고정 + 재현성 우선

1. Mission

Body(한국인 특화 mesh)와 Garment(템플릿/텍스처/측정치)를 결합해:

F1(A): 치수 기반 Fit Signal(ease) 산출(설명 가능/결정적)

F2(B): ROI 중심 SDF 기반 clipping 방어(온라인 최소 연산)

F3(Q): 품질검사(클리핑/체형붕괴/로고 훼손) 감지 후 필요 시 자동 재생성 루프 수행

생성 파이프라인용 조건 이미지(depth/normal) + provenance/품질점수/실패사유 출력

2. Product Contract
2.1 Inputs

Body (from Body Module)

body_mesh.npz (pose_id = PZ1 고정)

body_measurements_subset.json (토르소5+목, unit=m, warnings 포함)

prototype_id (SDF bank lookup key)

height_quant_2cm (delta 보정 provenance)

Garment (from Garment Module)

garment_proxy.npz (preferred)

fallback: garment_proxy_mesh.glb + garment_proxy_meta.json

(참고) garment_template_params.json은 Garment 모듈 내부용이며 Fitting 입력으로 사용하지 않음

garment_measurements_subset.json (bust/waist/hip, unit=m, optional)

garment_fit_hint.json (필수)

length_class(crop|regular|long), hemline_anchor, sleeve_end_anchor, collar_line_anchor

material_token + stretch_class (필수)

thickness_garment_m (필수; 없으면 material 기반 기본값 + warning)

garment_texture_latent + latent_meta.json(needs_reprocessing 포함) (G4 자산)

옵션(로고 보호 강화)

logo_anchor (템플릿/패널 좌표계 기준 로고 중심점)

2.2 Outputs

fit_signal.json

fitted_proxy.npz

condition_images/ (depth.png, normal.png)

provenance.json (버전키 + cache/solver/카메라 프리셋 + 루프 액션 기록)

3. Goals & Budget (TBD 금지)
3.1 Quality Goals

결정성: 동일 입력 + 동일 버전키 → 동일 output

Shirt MVP ROI(기본):

가슴(로고 패널), 겨드랑이/암홀, 셔츠 하단(엉덩이 상단 접촉부), 카라/목 라인(옵션)

3.2 Compute Budget (Fitting 단독, 루프 포함 상한)

Single-attempt p95 latency: <= 1.5s

End-to-end p95 latency(루프 포함): <= 3.0s

Max Retry: 2 (총 3회)

Online GPU compute time(총합): <= 0.6s

Peak VRAM: p95 <= 2GB, hard cap <= 3GB

SDF fetch p95(warm cache): <= 20ms

4. Non-Goals

full-body collision / full cloth simulation 금지

온라인 고비용 최적화 루프 금지(델타+경량 변형만)

카테고리 확장(바지/코트/패딩) MVP 범위 밖

5. Gates (운영 단호함)

(RevF 유지)

6. Interface Contract (Explainability + Camera + Retention)
6.1 fit_signal.json (필수 규격)

(RevF 유지)

6.2 Fixed Camera Invariance (필수: 생성 파이프라인 호환) — 좌표계 명시 보강(RevG)

고정 프리셋 ID: fixed_camera_preset_v1

Coordinate System: Right-Handed System (오른손 좌표계)

Axis: Y-up, Z-forward

Origin/Scale: Body 모듈의 원점/단위(meters) 규격을 그대로 따른다.

포함 파라미터(고정):

fov_deg, camera_distance_m, yaw/pitch/roll_deg

near/far, image_resolution

camera preset 변경은 오직 버전업으로만 허용하며,

변경 시 condition_image_version과 camera_preset_id 동시 변경 필수

6.3 Artifact Retention Policy

(RevF 유지: Hot Logs 30일, Summary 장기)

7. Core Algorithms

(RevF 유지)

8. Penalty & Severity

(RevF 유지: d_threshold_mm = max(2.2, 1.1*voxel_size_mm), 권장 2.5mm)

9. Score & Exposure Gate

score_total = 0.6*score_clipping + 0.25*score_fit_signal + 0.15*score_smoothness

score_total < 70 → 노출 금지 또는 degrade

score/penalty는 attempt별 기록(단, retention 적용)

10. Determinism Rules

경계값 비교는 정수화 후 비교

solver seed/순서 고정

단위 변환 중앙 유틸 강제(매직 넘버 금지)

camera_preset_id는 고정(변경은 버전업만)

11. Logo & Shape Distortion Sensors (품질 검사)
11.1 Area Stretch (가변 임계치)
𝐴
𝑟
𝑒
𝑎
𝑆
𝑡
𝑟
𝑒
𝑡
𝑐
ℎ
=
𝐴
𝑟
𝑒
𝑎
𝑐
𝑢
𝑟
𝑟
𝑒
𝑛
𝑡
𝐴
𝑟
𝑒
𝑎
𝑜
𝑟
𝑖
𝑔
𝑖
𝑛
𝑎
𝑙
AreaStretch=
Area
original
	​

Area
current
	​

	​


임계치: stretch_class 기반

stiff: 1.10 / normal: 1.15 / stretch: 1.25

실패: AreaStretch > AreaStretch_max → retry 신호

11.2 Aspect Ratio Defense

방향성 과도 신축 감지(임계치 테이블화)

실패 시 retry 신호

11.3 Spike/Shape Defense (ROI Laplacian residual)

ROI 한정 Laplacian residual p95/max

score_smoothness로 반영

11.4 Logo Center Shift (가변 임계치)

전제: Garment가 logo_anchor 제공

임계치: stiff 10mm / normal 15mm / stretch 20mm(최대 상한)

12. Automatic Regeneration Loop Policy (재생성 루프) — Solver/Inflate 보강(RevG)
12.2 Constraints (예산 + 메모리 + 수학적 안전장치)

Max Retry: 2

Total Timeout p95: 3.0s

Allowlist 기반 파라미터만 수정 가능

Memory Hygiene Rule: 각 attempt 시작 시 intermediate tensors/buffers/solver state 명시적 clear

Iteration Limit (필수): Constraint Solver의 최대 반복 횟수는 **시도당 N_iter_max = 100**을 초과할 수 없다.

(추후 버전업 가능하지만, 기본값은 문서 고정)

12.3 Retry Algorithm (경량 + 부드러운 팽창 + 반경 가이드)

Attempt 1: Tier-0 + Tier-1(기본 constraint)

Retry 1: constraint_strength +20% (solver 재계산)

Retry 2: Local Inflate(2~5mm) + Gaussian/Cosine falloff smoothing 필수

Inflate 영향 반경 가이드(필수):

falloff의 표준편차/반경(σ)은 해당 ROI의 대표 길이(scale)의 10~20% 범위로 제한한다.

목적: 너무 좁아 “혹”이 생기거나, 너무 넓어 “셔츠 핏이 무너지는” 현상 방지

12.4 Early Exit / Fast Fail

구제 불가 케이스는 빠르게 종료:

max_penetration_mm > 10 또는 Penalty 과대 등

Retry 1 스킵하여 Retry 2 직행 또는 즉시 Hard Fail

12.5 Audit (Retention 적용)

retry_history[]는 Hot Logs로 취급(30일)

13. Milestones

F0 Runner + Taxonomy 출력

F1 Body 연동(A)

F2 Garment 연동(A) + garment_fit_hint 계약 확정

F3 Tier-0 SDF Bank 생성(+ voxel_size_mm <= 2.0 규격 준수)

F3.5 Warm Cache 구현 + 텔레메트리

F4 Tier-1 Constraint Solver + penalty/score

F5 Condition image preprocessor(depth/normal) + fixed_camera_preset_v1

F6 Sensors + Regeneration Loop(timeout/max retry/memory clear + falloff inflate)

F7 Retention 정책 적용(Hot Logs TTL 30d + Summary 장기 보관)

14. Versioning

fitting_version

roi_policy_version

sdf_bank_version

sdf_cache_policy_version

constraint_version (iteration limit 포함)

smoothing_version (falloff 포함)

condition_image_version

camera_preset_id (fixed_camera_preset_v1)

body/garment 버전키를 provenance에 포함