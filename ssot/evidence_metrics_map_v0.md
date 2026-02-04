# Evidence & Metrics Map v0 (KPI/KPI_DIFF, 무엇을 어디서 보는가)

목표: "무슨 파일을 보면 무엇을 알 수 있는지"를 경로/파일 중심으로 고정한다.
링크는 사용하지 않고, 경로/파일명만 명시한다.

---

## 1) 비교 기준 (Baseline / Prev / Current)

### 1.1 Baseline (고정값)
- baseline_tag(alias): curated-v0-realdata-v0.1
- baseline_run_dir: exports/runs/curated_v0/round20_20260125_164801
- baseline_report: reports/validation/curated_v0_facts_round1.md
- lane: curated_v0

### 1.2 Prev (자동 추론)
- 동일 lane에서 시간상 가장 최근 run_dir
- prev 없음 → baseline_run_dir로 fallback (경고만, 빌드 안 깨짐)
- prev == baseline → KPI_DIFF == 0 수렴은 정상

### 1.3 Postprocess 엔트리포인트 (입력 3종 고정)
- tools/postprocess_round.py
  - current_run_dir
  - prev_run_dir
  - baseline_run_dir

---

## 2) 운영 관점 "무엇을 어디서 본다"

### 2.1 진행/언락 상태(모듈 단계 매트릭스)
- PROJECT_DASHBOARD.md
  - 모듈별 단계(B01/B02/F01/G01 등) done/total, UNLOCKED/BLOCKED를 한 화면에서 본다.
  - progress 로그 소스 경로(예): exports/progress/PROGRESS_LOG.jsonl

### 2.2 모듈별 "오늘 가능한 작업"과 "단일 차단 의존"
- BODY_WORK_BRIEF.md
- FITTING_WORK_BRIEF.md
- GARMENT_WORK_BRIEF.md

### 2.3 U1/U2 DoD(Freeze): 무엇이 필수 산출물인가
- unlock_conditions_u1_u2.md
  - U1 필수 산출물
  - 결측 정책(Soft/Degraded)
  - Garment Hard Gate / Early Exit
  - fitting_facts_summary 최소 필드

### 2.4 단위/표시 정밀도
- UNIT_STANDARD.md
  - canonical unit: m
  - display: 0.001m round-half-up 권장

### 2.5 무결성/경계(Guardrails)
- GUARDRAILS.md
  - import boundary 위반은 merge 차단(blocker)
  - cross-module import 제한 규칙

---

## 3) KPI / KPI_DIFF: 목적 및 확인 포인트

### 3.1 목적
- KPI: current_run_dir의 정량 지표 요약(측정/관측 기반)
- KPI_DIFF: prev/baseline 대비 변화 요약(운영 상 퇴행/개선 신호)

### 3.2 확인 포인트(경로)
- current_run_dir: exports/runs/<lane>/round*_YYYYMMDD_HHMMSS
- prev_run_dir: (자동 추론 결과)
- baseline_run_dir: (고정값)

### 3.3 KPI/KPI_DIFF 파일명/위치(확정)
- exports/runs/<lane>/<run_id>/KPI.json
- exports/runs/<lane>/<run_id>/KPI_DIFF.md

---