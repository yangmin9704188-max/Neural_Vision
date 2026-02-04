standard\_key,ko\_term,dimension,priority,notes
HUMAN\_ID,HUMAN\_ID,meta,must,개인 식별 키(통합용). 7th/8th에서 표기 변형 존재.
SEX,성별,meta,must,
AGE,나이,meta,must,ISO나이 존재 가능. v0는 '나이'를 기준으로 함.
HEIGHT\_M,키,height,must,단위 m로 ingestion에서 확정.
WEIGHT\_KG,몸무게,weight,must,단위 kg 가정(원천 단위 확인 필요).
HEAD\_CIRC\_M,머리둘레,circ,optional,마네킹 처리라도 상단 실루엣/비율 제약에 도움.
NECK\_CIRC\_M,목둘레,circ,must,
NECK\_WIDTH\_M,목너비,width,must,
NECK\_DEPTH\_M,목두께,depth,must,
SHOULDER\_WIDTH\_M,어깨너비,width,must,
CHEST\_CIRC\_M\_REF,가슴둘레,circ,ref,레거시/참조 전용(Deprecated CHEST).
BUST\_CIRC\_M,젖가슴둘레,circ,must,정책 이원화(BUST).
UNDERBUST\_CIRC\_M,젖가슴아래둘레(여),circ,must,정책 이원화(UNDERBUST). 남성은 결측 가능.
UNDERBUST\_WIDTH\_M,젖가슴아래너비,width,optional,3D/일부 소스 전용일 수 있음.
UNDERBUST\_DEPTH\_M,젖가슴아래두께,depth,optional,3D/일부 소스 전용일 수 있음.
CHEST\_WIDTH\_M,가슴너비,width,must,
CHEST\_DEPTH\_M,가슴두께,depth,must,
WAIST\_CIRC\_M,허리둘레,circ,must,
NAVEL\_WAIST\_CIRC\_M,배꼽수준허리둘레,circ,must,
ABDOMEN\_CIRC\_M,배둘레,circ,optional,
WAIST\_WIDTH\_M,허리너비,width,must,
WAIST\_DEPTH\_M,허리두께,depth,must,
NAVEL\_WAIST\_WIDTH\_M,배꼽수준허리너비,width,must,
NAVEL\_WAIST\_DEPTH\_M,배꼽수준허리두께,depth,must,
HIP\_CIRC\_M,엉덩이둘레,circ,must,
HIP\_WIDTH\_M,엉덩이너비,width,must,
HIP\_DEPTH\_M,엉덩이두께,depth,must,
UPPER\_HIP\_CIRC\_M,Upper-hip둘레,circ,optional,8th\_3d 전용 가능.
TOP\_HIP\_CIRC\_M,Top-hip둘레,circ,optional,8th\_3d 전용 가능.
UPPER\_ARM\_CIRC\_M,위팔둘레,circ,optional,
ELBOW\_CIRC\_M,팔꿈치둘레,circ,optional,
WRIST\_CIRC\_M,손목둘레,circ,optional,
ARM\_LEN\_M,팔길이,length,must,
CROTCH\_HEIGHT\_M,샅높이,height,must,하의 핏/비율 제약 핵심.
KNEE\_HEIGHT\_M,무릎높이,height,optional,
CROTCH\_FB\_LEN\_M,샅앞뒤길이,length,optional,
BACK\_LEN\_M,등길이,length,must,상의 패턴 핵심.
FRONT\_CENTER\_LEN\_M,앞중심길이,length,optional,상의 패턴 보조.
THIGH\_CIRC\_M,넙다리둘레,circ,must,
MID\_THIGH\_CIRC\_M,넙다리중간둘레,circ,optional,
KNEE\_CIRC\_M,무릎둘레,circ,optional,
BELOW\_KNEE\_CIRC\_M,무릎아래둘레,circ,optional,
CALF\_CIRC\_M,장딴지둘레,circ,optional,
MIN\_CALF\_CIRC\_M,종아리최소둘레,circ,optional,
ANKLE\_MAX\_CIRC\_M,발목최대둘레,circ,optional,

