# M0 Runbook v1 (Fitting)

## 목적
- Upstream(Body/Garment) 없이도 Fitting U1 최소 산출물을 생성한다.
- 생성 산출물:
  - `geometry_manifest.json`
  - `fitting_facts_summary.json`

## 실행
레포 루트에서 실행:

```bash
py modules/fitting/tools/run_fitting_m0_harness.py --mode ok
```

옵션:
- `--mode ok|degraded|hard_gate`
- `--garment-input-used npz|glb_fallback` (기본: `glb_fallback`)
- `--run-id <id>`
- `--out-root <dir>`

기본 출력 경로:
- `modules/fitting/runs/m0/<run_id>/`

## U1 검증
하네스 출력의 `[M0_RUN_DIR]` 경로를 `<RUN_DIR>`로 사용:

```bash
py tools/validate/validate_u1_fitting.py --run-dir <RUN_DIR>
```

성공 기준:
- `VALIDATE SUMMARY`가 `PASS` 또는 `WARN`
- 종료코드 `0` (`FAIL=0` 조건 충족)

## 예상 WARN 패턴
M0에서 Body/Garment 실아티팩트를 두지 않는 경우 다음 WARN은 허용:
- `input_priority`: run-dir 내 `garment_proxy.npz`/`.glb` 부재 경고

## 모드별 기대
- `ok`: `early_exit=false`, `degraded_state=none`
- `degraded`: `early_exit=false`, `degraded_state=high_warning_degraded`
- `hard_gate`: `early_exit=true`, `early_exit_reason` 문자열
