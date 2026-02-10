# Standard Measurement Keys Dictionary

표준 키 사전의 단일 진실원.

## Standard Keys

| standard_key | dimension | unit | meaning |
|-------------|-----------|------|---------|
| HUMAN_ID | meta | | 개인 식별 키(통합용) |
| SEX | meta | | 성별 |
| AGE | meta | | 나이 |
| HEIGHT_M | height | m | 키 |
| WEIGHT_KG | weight | kg | 몸무게 |
| HEAD_CIRC_M | circ | m | 머리둘레 |
| NECK_CIRC_M | circ | m | 목둘레 |
| NECK_WIDTH_M | width | m | 목너비 |
| NECK_DEPTH_M | depth | m | 목두께 |
| SHOULDER_WIDTH_M | width | m | 어깨너비 |
| CHEST_CIRC_M_REF | circ | m | 가슴둘레 (참조 전용, Deprecated CHEST) |
| BUST_CIRC_M | circ | m | 젖가슴둘레 |
| UNDERBUST_CIRC_M | circ | m | 젖가슴아래둘레(여) |
| UNDERBUST_WIDTH_M | width | m | 젖가슴아래너비 |
| UNDERBUST_DEPTH_M | depth | m | 젖가슴아래두께 |
| CHEST_WIDTH_M | width | m | 가슴너비 |
| CHEST_DEPTH_M | depth | m | 가슴두께 |
| WAIST_CIRC_M | circ | m | 허리둘레 |
| NAVEL_WAIST_CIRC_M | circ | m | 배꼽수준허리둘레 |
| ABDOMEN_CIRC_M | circ | m | 배둘레 |
| WAIST_WIDTH_M | width | m | 허리너비 |
| WAIST_DEPTH_M | depth | m | 허리두께 |
| NAVEL_WAIST_WIDTH_M | width | m | 배꼽수준허리너비 |
| NAVEL_WAIST_DEPTH_M | depth | m | 배꼽수준허리두께 |
| HIP_CIRC_M | circ | m | 엉덩이둘레 |
| HIP_WIDTH_M | width | m | 엉덩이너비 |
| HIP_DEPTH_M | depth | m | 엉덩이두께 |
| UPPER_HIP_CIRC_M | circ | m | Upper-hip둘레 |
| TOP_HIP_CIRC_M | circ | m | Top-hip둘레 |
| UPPER_ARM_CIRC_M | circ | m | 위팔둘레 |
| ELBOW_CIRC_M | circ | m | 팔꿈치둘레 |
| WRIST_CIRC_M | circ | m | 손목둘레 |
| ARM_LEN_M | length | m | 팔길이 |
| CROTCH_HEIGHT_M | height | m | 샅높이 |
| KNEE_HEIGHT_M | height | m | 무릎높이 |
| CROTCH_FB_LEN_M | length | m | 샅앞뒤길이 |
| BACK_LEN_M | length | m | 등길이 |
| FRONT_CENTER_LEN_M | length | m | 앞중심길이 |
| THIGH_CIRC_M | circ | m | 넙다리둘레 |
| MID_THIGH_CIRC_M | circ | m | 넙다리중간둘레 |
| KNEE_CIRC_M | circ | m | 무릎둘레 |
| BELOW_KNEE_CIRC_M | circ | m | 무릎아래둘레 |
| CALF_CIRC_M | circ | m | 장딴지둘레 |
| MIN_CALF_CIRC_M | circ | m | 종아리최소둘레 |
| ANKLE_MAX_CIRC_M | circ | m | 발목최대둘레 |

## Notes

- Coverage v0: 45 standard keys enumerated (based on measurement_coverage_v0.csv).
- All measurement keys use unit `m` (meters) or `kg` (kilograms) as specified.
- Meta keys (HUMAN_ID, SEX, AGE) have no unit.
- `CHEST_CIRC_M_REF` is reference-only and deprecated. Use `UNDERBUST_CIRC_M` / `BUST_CIRC_M` instead.
- Legacy CHEST keys are deprecated. Use UNDERBUST_CIRC_M / BUST_CIRC_M instead.
