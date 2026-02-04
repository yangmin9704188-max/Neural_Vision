src/
  runners/        # run_geo... 같은 실행 엔트리
  pipeline/       # end-to-end 파이프라인 (입력→전처리→측정→출력)
  measurements/   # 순수 측정 알고리즘(둘레/폭/길이/hull/slice)
  io/             # 로더/세이버/manifest/schema/writers
  quality/        # gate/quality score/센서
  utils/          # 단위변환, 타입, 수치안정성

runners/는 얇게(파라미터 받고 pipeline 호출만)

알고리즘은 measurements/에 몰아 넣고, IO/계약은 io/에서만 다루게 제한