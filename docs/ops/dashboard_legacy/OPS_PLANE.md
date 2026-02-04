# Ops Plane Charter

## 목적

Ops Plane은 1인 개발 환경에서 에너지 소모를 최소화하고, 투명성/추적성/회귀 안전장치를 제공하는 운영 체계입니다.

## Single Source of Truth (SoT)

Ops Plane의 SoT는 다음 Git 경로로 관리됩니다:

- `SYNC_HUB.md`: 프로젝트 전략 및 마스터 플랜
- `docs/sync/CURRENT_STATE.md`: 현재 프로젝트 상태
- `.cursorrules`: Cursor AI 작업 규칙
- `docs/ops/cursor_prompt_header.md`: Cursor 프롬프트 헤더
- `docs/ops/pr_bodies/**`: PR 본문 템플릿
- `docs/ops/COMMANDS.md`: 공식 단축 명령 목록
- `.github/workflows/**`: CI/CD 워크플로우

## 운영 포인트

### CI Green 원칙
- **CI green일 때만 merge**: 모든 CI 체크가 통과한 경우에만 PR 머지 허용

### Guard Hit 처리
- Guard hit 누적 시 "백필 PR 1개로 사실 기록 복구" 후 재발 방지 강화
- 구조 오염(Import 경계 위반)은 Blocker로 처리하여 merge 차단

### 자동 문서 생성 격리
- 환경차에 취약한 자동 문서 생성은 Warning으로 격리
- Blocker는 구조 오염만 대상으로 함

## 참고 문서

- [Guardrails](GUARDRAILS.md): Import 경계 검사 및 구조 오염 방지 규칙
- [Backfill Policy](BACKFILL_POLICY.md): Tier 0/1/2 백필 정책
- [Backfill Log](BACKFILL_LOG.md): Tier2 백필 실행 기록
- [Rounds README](rounds/README.md): 라운드 기록 규칙 및 템플릿

## 봉인 상태

- **Ops Plane sealed at tag opsplane-v1** (merge commit a80aec0)
- **Architecture v1 sealed at tag arch-v1** (merge commit 9166fe4)
- 이후 구조 변경은 v2 문서 "추가"로만 진행하며, 기존 v1 문서 수정은 금지됩니다.
