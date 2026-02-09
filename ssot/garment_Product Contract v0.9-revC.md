Garment Product Contract v0.9-revC
Scope: Shirt-only MVP / Template Proxy Mesh + Texture DNA (Offline)
Primary Output: garment\_proxy\_mesh + garment\_latent\_asset
B2B Core: 입력 무결성(GIGO) + 오프라인 가공(비용 절감) + 템플릿 확장성(진입장벽)

1. Module Mission

ControlNet (구조 가이드): body\_mesh + garment\_proxy\_mesh (+ depth/normal)로 구조적 일관성을 제공

IP-Adapter (질감 가이드): Swatch 기반 Texture DNA(offline) 저장 → 온라인은 latent 로드

운영 원칙

조용한 오답 금지(모든 추정엔 provenance/warnings)

Hard Gate는 치명적만 / 나머지는 Soft + 재업로드 루프

2. External Seller Intake Contract (G0)
   2.1 Required (Hard)

front\_view\_image, side\_view\_image, back\_view\_image

hero\_image

material\_token (enum)

2.2 Optional (Soft)

swatch\_image (권장)

weight\_class (선택; light|medium|heavy) (revC 추가)

목적: 두께/신축/낙하감 추정 보조(판매자 부담 낮은 선택지)

2.3 Intake Policy

기본: 진단 + 가이드 + 재업로드 루프

예외: G1.5 Hard Gate 실패 시 업로드 거부 + 재촬영 요청

3. Canonicalization v0 (G1)

(변경 없음)

4. Fabric Swatch + Gatekeeper v0 (G1.5)
   4.1 Outputs

fabric\_swatch.png

fabric\_swatch\_quality.json

4.2 Gatekeeper Metrics (필수 기록)

기본 품질 지표

mask\_validity\_score

swatch\_area\_ratio

edge\_density

gradient\_variance

highlight\_ratio

moire\_score

일관성/타일링 방어

color\_consistency\_delta

pattern\_consistency\_score

tileability\_score

self\_similarity\_score

이물질(불순물) 감지기 — Object Detection (revC 필수 추가)

foreign\_object\_score

foreign\_object\_types\[] (예: button|stitch\_seam|zipper|label|logo\_fragment|specular\_blob)

foreign\_object\_bbox\_count

정책: Swatch crop 영역 내에서 단추/봉제선/라벨/로고 조각/스티치 라인 등 “반복 전파 위험 요소”를 경량 detector로 탐지한다.

구현 방식은 자유(룰 기반 + 간단 모델 조합 가능)이나, 계약상 ‘탐지 수행 및 결과 기록’은 필수다.

4.3 Gate Policy (2단)

Hard Gate (업로드 거부; 치명적만)

마스크 실패/누출 심각: mask\_validity\_score 임계치 미만

해상도 극저

swatch 면적 부족: swatch\_area\_ratio 임계치 미만

Soft Gate (경고 + 확인/재업로드 루프)

주름/그림자/반사/모아레 과다

Hero vs Swatch 불일치: COLOR\_PATTERN\_INCONSISTENT

타일 불가/불순물 의심: SWATCH\_NOT\_TILEABLE

이물질 탐지: SWATCH\_FOREIGN\_OBJECT\_DETECTED

foreign\_object\_score 임계치 초과 시 경고

UI: “단추/봉제선 없는 면으로 스와치 재촬영” 가이드 + heatmap/bbox 오버레이 제공

원칙: 이물질 탐지는 기본 Soft로 시작(오탐/이탈 방지). 단, 반복적으로 실패하는 판매자/브랜드는 “강화 모드”를 운영 옵션으로 적용 가능.

4.4 Seller UI Requirements

“조명/주름/배경” 3대 요소 가이드 라벨

heatmap overlay 제공 + “재촬영 액션” 제안(구체적 지시)

Soft Gate는 확인 루프(swatch 재업로드/재촬영)로 유도한다.

5. Shirt Template Proxy Mesh System v0 (G2)
   목적: “완벽한 3D 복원”이 아니라 ControlNet에 유효한 구조 가이드 프록시 제공

5.1 Template System

Base parts: torso / sleeve / collar

Variant layer (MVP): regular / overfit / drop\_shoulder / raglan

Detail anchors (필수):

neckline, shoulder\_seam, cuff\_end, button\_placket, hemline

logo\_panel (로고 상품일 경우 필수 운영)

5.2 Matching Principle

전역 실루엣 1:1 완벽 매칭이 아니라,

앵커 정합(anchor alignment) 중심 + 부드러운 warp로 충분히 그럴듯한 구조를 만든다.

단, warp가 과도하면 품질이 붕괴하므로 왜곡 점수 기반 Gate를 적용한다.

5.3 Outputs (Hard Required)

garment\_proxy\_mesh.glb (표준)

garment\_proxy\_meta.json

garment\_proxy\_meta.json (필수 필드)

(기존 필드 유지 + 아래 보강)

mesh\_distortion\_score (0~100)

warp\_metrics:

max\_stretch\_ratio

max\_shear

max\_bend 또는 curvature\_residual

self\_intersection\_flag

negative\_face\_area\_flag (revC 추가, 필수)

의미: triangle flip/정점 순서 뒤집힘 등으로 면적이 음수로 계산되는 면이 존재하는지

목적: 피팅 단계 SDF/연산 폭주(NaN/무한루프) 원천 차단

6. ControlNet 조건 이미지 Pre-Processor (G2.1, Tools)

위치: Garment 모듈이 아니라 공용 tools 레이어(재사용/실험 속도)

6.1 Input

garment\_proxy\_mesh.glb

camera\_preset\_id

6.2 Output

depth.png, normal.png (+ optional: silhouette.png, canny.png)

카메라 프리셋은 Body/Fitting과 동일 규격을 사용한다.

fixed\_camera\_preset\_v1 (Right-handed, Y-up, Z-forward, meters)

7. ROI-aware Template Refinement (G3)

목적: 비용 폭주 없이 ROI(클레임 빈발 영역)에서만 정밀도 상승

7.1 ROI Targets (MVP)

armhole

collar\_to\_neck

chest\_logo\_panel

upper\_hip\_contact

7.2 Principle

전역 정밀화 금지. ROI에서만 refinement 수행

결과는 mesh\_distortion\_score / warp\_metrics에 반영되어야 한다.

8. Texture DNA Offline Processing (G4)

목적: 업로드 시 1회 고비용 허용 → 온라인은 latent 로드만

8.1 Outputs (Hard Required)

garment\_latent\_asset/

embedding.(pt|npy) (필수)

style\_map.(pt|npy) (옵션; 프리미엄 SKU)

latent\_meta.json (필수)

latent\_meta.json (필수 필드)

garment\_id

encoder\_name

encoder\_version

ip\_adapter\_compat\_version (또는 텍스처 인코더 대응 버전)

latent\_generation\_config\_hash (필수; 설정/전처리/정규화 지문)

created\_at

swatch\_quality\_summary (G1.5 요약)

needs\_reprocessing (필수)

정의: IP-Adapter/encoder 변경 등으로 기존 DNA가 최신 스택과 호환되지 않을 가능성이 있을 때 true

운영: needs\_reprocessing=true 자산은 오프라인 재가공 배치 작업 대상

8.2 MVP 운영 리스크 방어(필수 포함)

임베딩 재사용이 불가능한 스택일 경우 경량 인코딩 fallback을 제공해야 한다.

fallback 사용 시 warnings\[]에 LATENT\_FALLBACK\_USED 기록

9. Material Token v1 (G5)
   9.1 Outputs (Hard Required)

prompt\_snippet, negative\_snippet

stretch\_class (stiff|normal|stretch)

thickness\_garment\_m

9.2 Thickness Default Policy (운영 규칙)

판매자 입력이 없으면 material\_token 기반 표준 테이블로 자동 채움

THICKNESS\_DEFAULTED 경고 기록

Material Thickness Default Table (초기 운영값)

cotton\_oxford: 0.0005 m

linen: 0.0003 m

denim: 0.0008 m

poly\_blend: 0.0004 m

9.3 Thickness Extension Hooks (revC 추가; MVP는 옵션)

weight\_class(G0 선택 입력)가 제공되면, thickness\_garment\_m의 스케일 팩터로 사용 가능:

light: 0.8x, medium: 1.0x, heavy: 1.2x (초기 운영값, 버전업으로만 변경)

edge\_density 등 swatch 지표를 이용한 \*\*자동 미세조정은 MVP에서 “권장 연구/확장”\*\*으로 남긴다.

적용 시 반드시 THICKNESS\_FINE\_TUNED 경고/프로비넌스 기록

10. Quality Gates Summary (Garment-side)
    10.1 Hard Gates

material\_token 누락 → 거부

G1.5 Hard Gate 실패 → 거부 + 재촬영 루프

garment\_proxy\_mesh 또는 fit\_hint 누락 → 거부

stretch\_class 누락 → 거부

thickness\_garment\_m 누락 → (기본값 자동 채움 후 진행) + THICKNESS\_DEFAULTED

has\_logo=true 인데 logo\_anchor=null → 거부

mesh\_distortion\_score < 40 → 거부

self\_intersection\_flag=true → 거부

negative\_face\_area\_flag=true → 거부 (revC 필수 추가)

10.2 Soft Gates

40 <= mesh\_distortion\_score < 70 → 경고 + warp 과다 표시

COLOR\_PATTERN\_INCONSISTENT → 경고 + 확인/재업로드 루프

SWATCH\_NOT\_TILEABLE → 경고 + 재촬영 루프

SWATCH\_FOREIGN\_OBJECT\_DETECTED → 경고 + bbox/heatmap 기반 재촬영 루프

11. Versioning (필수)

garment\_contract\_version = v0.9-revC

template\_system\_version

anchor\_schema\_version

material\_policy\_version

swatch\_gatekeeper\_version

texture\_dna\_version

camera\_preset\_id = fixed\_camera\_preset\_v1

12. Artifact Retention

원본 업로드 이미지 보관은 파트너 계약에 따르되, 운영 계층을 분리한다.

Hot Debug Artifacts(heatmap/중간 산출물): 30일

Business Assets(proxy mesh/meta + latent/meta): 장기 보관(스토리지 계층 분리)

삭제/샘플링 정책 변경은 retention\_policy\_help.md 같은 운영 문서로만 버전 관리

