# DoriLab Engineering Source Register v0.2

기준일: 2026-09-14. 27개 자료를 선정했다. 논문, 기술보고서, 발표자료, 기술회보를 구분한다. `CATALOG_ABSTRACT_CHECKED`는 서지·초록을 확인했다는 뜻이며, 본문에서 학습사례를 추출했다는 뜻이 아니다. 원본 PDF는 이번 패키지에 포함하지 않았다.

기존 출처 2개: TH-01 및 VB-X1. 기존 원문·사례 파일은 `legacy/PhysicsSeed32_v01/`에 보존했다. 저작권 문구는 출처 페이지의 표시이며, 실제 사용하는 부분과 조직의 이용 조건에 대한 검토는 `data/source_review.csv`로 기록한다.

| ID | 영역 | 연도 | 유형 | 우선순위 / 용도 | 확인 범위 |
|---|---|---|---|---|---|
| VB-X1 | MECHANICS | 2015 | Journal article | P0 / TRAIN_CANDIDATE | FULLTEXT_SECTION_CHECKED |
| VB-03 | MECHANICS | 2012 | NASA Technical Memorandum | P1 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MEC-03 | MECHANICS | 2014 | Conference paper | P1 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MEC-04 | MECHANICS | 2015 | Technical bulletin | P2 / REFERENCE_ONLY | CATALOG_ABSTRACT_CHECKED |
| VB-S1 | MECHANICS | 2019 | Conference Paper | P1 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MEC-06 | MECHANICS | 2010 | Presentation | P2 / DEV_RESERVED | CATALOG_ABSTRACT_CHECKED |
| TH-01 | THERMAL | 1971 catalogue / 1972 PDF | NASA Technical Note | P0 / TRAIN_CANDIDATE | LEGACY_BODY_CHECKED |
| TH-03 | THERMAL | 2009 | Conference Paper | P1 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| TH-D1 | THERMAL | 2022 | Journal article | P1 / DEV_RESERVED | CATALOG_ABSTRACT_CHECKED |
| TH-S1 | THERMAL | 2015 | Conference Paper | P1 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |
| TH-05 | THERMAL | 2003 | Other (NTRS classification) | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| EE-01 | EEE | 1992 | NASA Technical Memorandum | P1 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| EE-02 | EEE | 1999 | Contractor Report | P1 / TRAIN_CANDIDATE | FULLTEXT_SECTION_CHECKED |
| EE-03 | EEE | 2022 cover; report date 2023-04-12 | NASA Technical Memorandum | P2 / TRAIN_CANDIDATE | FULLTEXT_SECTION_CHECKED |
| EE-04 | EEE | 2024 | Technical report | P2 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MAT-01 | MATERIALS | 1984 | NASA Reference Publication | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MAT-02 | MATERIALS | 1995 | Conference paper | P2 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MAT-03 | MATERIALS | 2010 | NASA Technical Memorandum | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| MAT-04 | MATERIALS | 2017 | Conference paper / tutorial | P2 / REFERENCE_ONLY | CATALOG_ABSTRACT_CHECKED |
| FL-01 | FLUID_PRESSURE | 1989 | NASA Technical Memorandum | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| FL-02 | FLUID_PRESSURE | 1974 | Contractor Report | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| FL-03 | FLUID_PRESSURE | 2009 | Contractor Report | P2 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |
| FL-04 | FLUID_PRESSURE | 1993 | Other (NTRS classification) | P2 / DEV_RESERVED | CATALOG_ABSTRACT_CHECKED |
| SW-01 | SOFTWARE_HIL | 2023 conference | Conference paper | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| SW-02 | SOFTWARE_HIL | 2008 | Conference paper | P2 / TRAIN_RESERVED | CATALOG_ABSTRACT_CHECKED |
| SW-03 | SOFTWARE_HIL | 2017 | Conference paper | P2 / DEV_RESERVED | CATALOG_ABSTRACT_CHECKED |
| SW-04 | SOFTWARE_HIL | 2025 | arXiv preprint / conference contribution | P2 / EVAL_RESERVED | CATALOG_ABSTRACT_CHECKED |

## VB-X1 — Force limited random vibration testing: the computation of the semi-empirical constant C² for a real test article and unknown supporting structure

저자: J. J. Wijker, M. H. M. Ellenbroek, A. de Boer
발행: 2015 / Journal article
식별번호: 해당 없음 / DOI: 10.1007/s12567-015-0086-0

공식 출처: https://link.springer.com/article/10.1007/s12567-015-0086-0
원문 후보: https://link.springer.com/content/pdf/10.1007/s12567-015-0086-0.pdf

권리 표기: CC BY 4.0
확인 수준: FULLTEXT_SECTION_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: JWST_MIRI_IFLV, ISS_LINEAR_DRIVE_UNIT, WIJKER_FORCE_LIMIT_REANALYSIS
권장 사용: P0 / TRAIN_CANDIDATE

**학습 목표 — DoriLab 설계 제안**
지지구조 임피던스와 시험품 응답을 구분한다; 계수 C² 및 기준 모드의 입력 근거를 검토한다

**읽을 부분**
본문 방법 정의, 모달 입력과 적용범위; 기존 SF-VBX1-01~08 및 16개 사례 재검토

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
계수·모드 선정 근거가 없는 경우와 충족된 경우를 짝으로 비교한다

**보충 기록**
기존 16개 사례 보존. JWST/MIRI·ISS Linear Drive Unit 재분석을 포함하므로 관련 시험 프로그램과 평가 분리 검토.

## VB-03 — Application of the Semi-Empirical Force-Limiting Approach for the CoNNeCT SCAN Testbed

저자: Lucas D. Staab, Mark E. McNelis, James C. Akers, Vicente J. Suarez, Trevor M. Jones
발행: 2012 / NASA Technical Memorandum
식별번호: NASA/TM-2012-217627 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20120014221
원문 후보: https://ntrs.nasa.gov/api/citations/20120014221/downloads/20120014221.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: CONNECT_SCAN
권장 사용: P1 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
계산한 force limit와 실제 시험 응답을 연결한다; 시험 입력·응답·계측 데이터의 역할을 분리한다

**읽을 부분**
본문 확보 후 계수 선정, 시험 구성, 분석-시험 비교, lessons learned 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
같은 시험품의 예측과 측정을 연결하는 사례; 수치 전사 전 표·축·단위 확인

## MEC-03 — High Gain Antenna System Deployment Mechanism Integration, Characterization, and Lessons Learned

저자: Fil Parong, Blair Russell, Walter Garcen, Chris Rose, Chris Johnson, Craig Huber
발행: 2014 / Conference paper
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20150004047
원문 후보: https://ntrs.nasa.gov/api/citations/20150004047/downloads/20150004047.pdf

권리 표기: Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: GPM_HGAS
권장 사용: P1 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
중력 보상장치의 영향을 제품 거동과 분리한다; 간섭 이상과 동적 모델의 검토를 연결한다

**읽을 부분**
시험 구성·gravity negation·간섭 발견 및 해결 절을 원문 확보 후 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
보상장치에 의한 지연과 제품 간섭을 구별할 추가 증거 선택

## MEC-04 — NASA Engineering and Safety Center Technical Bulletin No. 15-02: Best Practices for Use of Sine Burst Testing

저자: Dexter Johnson
발행: 2015 / Technical bulletin
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20240000431
원문 후보: https://ntrs.nasa.gov/api/citations/20240000431/downloads/TB%2015%2002%20SINE%20BURST%20TESTING.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: NESC_SINE_BURST_GUIDANCE
권장 사용: P2 / REFERENCE_ONLY

**학습 목표 — DoriLab 설계 제안**
정적하중 검증 대안으로 사용하는 sine burst의 적용 전제를 찾는다

**읽을 부분**
기술회보 전체, 적용 가능한 하드웨어와 위험 완화; 최신 프로젝트 기준과 별도 관리

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
시험 선택의 전제를 확인하는 검토 항목 설계. 이 회보만으로 범용 시험레벨을 생성하지 않음

**보충 기록**
2015 발행, NTRS 2024 취득. 학술논문과 구분한 참고 회보.

## VB-S1 — European Service Module - Structural Test Article (E-STA) Building Block Test Approach and Model Correlation Observations

저자: James P. Winkel, Samantha A. Bittinger, Vicente J. Suarez, James C. Akers
발행: 2019 / Conference Paper
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20190001819
원문 후보: https://ntrs.nasa.gov/api/citations/20190001819/downloads/20190001819.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: ORION_ESM_ESTA
권장 사용: P1 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
부분조립체와 시스템 모델의 검증 계층을 구분한다; 센서 배치·하중경로 모델링 증거를 확인한다

**읽을 부분**
개발 담당과 분리된 평가 작성자가 원문 시험·계측·모델 상관 절을 검토

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
새 하드웨어의 독립 평가 후보; 같은 E-STA 후속 발표자료도 동일 그룹

## MEC-06 — De-Trending Techniques: Methods for Cleaning Questionable Shock Data

저자: Vincent J. Grillo
발행: 2010 / Presentation
식별번호: KSC-2011-015R; KSC-2010-227 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20110001424
원문 후보: https://ntrs.nasa.gov/api/citations/20110001424/downloads/20110001424.pdf

권리 표기: Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: KSC_SHOCK_DETREND_METHOD
권장 사용: P2 / DEV_RESERVED

**학습 목표 — DoriLab 설계 제안**
센서 영점이동과 물리적 충격응답을 구분한다; 보정으로 복구할 수 있는 데이터의 한계를 확인한다

**읽을 부분**
본문 확보 후 drift·velocity/displacement·retest 판단 슬라이드 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
과도한 보정으로 통과 결론을 만드는 경우와 재계측 근거를 요청하는 경우 비교

## TH-01 — Apollo Telescope Mount Thermal Systems Unit Thermal Vacuum Test

저자: H. F. Trucks, Uwe Hueter, J. H. Wise, F. D. Bachtel
발행: 1971 catalogue / 1972 PDF / NASA Technical Note
식별번호: NASA-TN-D-6646 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/19720011230
원문 후보: https://ntrs.nasa.gov/api/citations/19720011230/downloads/19720011230.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: LEGACY_BODY_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: ATM_TSU
권장 사용: P0 / TRAIN_CANDIDATE

**학습 목표 — DoriLab 설계 제안**
측정 위치와 모델 노드의 물리량을 연결한다; 경계조건·열용량·계측 영향의 원인 후보를 구별한다

**읽을 부분**
기존 SF-TH01-01~08, 16개 사례와 PDF 위치를 다시 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
기존 대조쌍을 보존하고 서브도메인·판단 개념 태그를 추가

**보충 기록**
기존 패키지의 본문 텍스트 확인 이력을 승계. NTRS 등록1971-03, PDF1972-03 차이 보존; 표·그림 숫자 재추출은 미완료.

## TH-03 — A Physics-Based Temperature Stabilization Criterion for Thermal Testing

저자: Steven L. Rickman, Eugene K. Ungar
발행: 2009 / Conference Paper
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20090037689
원문 후보: https://ntrs.nasa.gov/api/citations/20090037689/downloads/20090037689.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: THERMAL_STABILITY_METHOD
권장 사용: P1 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
온도 변화율과 잔여 과도응답의 관계를 검토한다; 열용량·열전달 특성이 안정화 판단에 미치는 영향을 찾는다

**읽을 부분**
본문의 stabilization criterion 정의·가정·비교절, 기준식의 단위 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
고정 dT/dt만 제공된 경우와 시험체 물리특성을 함께 평가한 경우 비교

**보충 기록**
이전 패키지에는 본문 접근 이력이 있지만 이번 커리큘럼의 신규 사례는 아직 미작성.

## TH-D1 — Transient thermal parameters correlation of spacecraft thermal models against test results

저자: Iñaki Garmendia, Eva Anglada
발행: 2022 / Journal article
식별번호: 해당 없음 / DOI: 10.1016/j.actaastro.2022.07.014

공식 출처: https://dsp.tecnalia.com/items/69c999d9-edd2-4b36-95cb-2ffedfb0218b
원문 후보: https://dsp.tecnalia.com/bitstreams/44f57fa6-857e-40b0-b500-e79503277642/download

권리 표기: CC BY 4.0
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: TRIBOLAB_ISS_TMM
권장 사용: P1 / DEV_RESERVED

**학습 목표 — DoriLab 설계 제안**
전도·복사·열관성 파라미터의 식별 조건을 검토한다; 여러 load case와 물리 제약의 역할을 이해한다

**읽을 부분**
본문 식별 문제·파라미터 제약·검증절; 논문 내 TRIBOLAB 데이터 그룹 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
새 경계조건의 모델 적합성 판단을 개발 평가로 구성

**보충 기록**
이전 패키지의 Creative Commons 확인 이력 승계; 신규 수치 전사 전 파일·라이선스 재확인.

## TH-S1 — Thermal Testing and Model Correlation of the Magnetospheric Multiscale (MMS) Observatories

저자: Jong S. Kim, Nicholas M. Teti
발행: 2015 / Conference Paper
식별번호: ICES-2015-331 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20150018320
원문 후보: https://ntrs.nasa.gov/api/citations/20150018320/downloads/20150018320.pdf

권리 표기: Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: MMS_OBSERVATORIES
권장 사용: P1 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
고온·저온·생존·과도 상태별로 증거를 분리한다; 모델 상관의 목적·조건과 근거범위를 검토한다

**읽을 부분**
독립 평가 작성자가 시험 case·센서·상관 방법 절을 검토

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
열모델 상관 및 운용 상태 조합의 미사용 프로그램 평가

## TH-05 — Thermal Vacuum Testing of a Novel Loop Heat Pipe Design for the Swift BAT Instrument

저자: Laura Ottenstein, Jentung Ku, David Feenan
발행: 2003 / Other (NTRS classification)
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20030022742
원문 후보: https://ntrs.nasa.gov/api/citations/20030022742/downloads/20030022742.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: SWIFT_BAT_LHP
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
기동·부하·열싱크 조건에 따른 검증범위를 구분한다; 모사 열원·열용량과 실제 장비의 대응을 확인한다

**읽을 부분**
본문 확보 후 LHP 설계·시험체·기동/부하/싱크 시험 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
정상상태 성능만으로 기동 성능까지 포함하는 결론을 검토

**보충 기록**
Thermal이 primary, Fluid가 secondary. 같은 Swift BAT 캠페인은 분할하지 않음.

## EE-01 — Stability testing and analysis of a PMAD dc test bed for the Space Station Freedom

저자: Robert M. Button, Andrew S. Brush
발행: 1992 / NASA Technical Memorandum
식별번호: NASA-TM-105846 / DOI: 10.4271/929297

공식 출처: https://ntrs.nasa.gov/citations/19920022038
원문 후보: https://ntrs.nasa.gov/api/citations/19920022038/downloads/19920022038.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: SSF_PMAD_DC_TESTBED
권장 사용: P1 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
정전력 부하의 입력 특성과 전원-부하 임피던스를 연결한다; 안정성 결론의 부하조건 범위를 확인한다

**읽을 부분**
본문 확보 후 source/load impedance 측정과 안정성 판정절

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
벤치 전원 안정성을 다른 버스·부하조건으로 이전할 때 필요한 증거 선택

## EE-02 — Integrated Advanced Microwave Sounding Unit-A (AMSU-A): Electromagnetic Interference and Electromagnetic Compatibility Test Report, MetSat/MetOp AMSU-A1

저자: A. Valdez
발행: 1999 / Contractor Report
식별번호: NASA/CR-1999-209494; Report 11411 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20000021554
원문 후보: https://ntrs.nasa.gov/api/citations/20000021554/downloads/20000021554.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: FULLTEXT_SECTION_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: AMSU_A1_EMI_EMC_SN105
권장 사용: P1 / TRAIN_CANDIDATE

**학습 목표 — DoriLab 설계 제안**
전후 baseline과 주입 시험 중 계측을 구별한다; 이상 신호와 주입 자극의 시간 대응을 확인한다

**읽을 부분**
PDF 11~14쪽 §1.1~1.6, 특히 PDF14쪽 시험자료 평가 방법; 상세 시험표는 추가 시각 검토

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
기능이 정상으로 복귀한 사실과 시험 중 간섭이 없었다는 결론을 구분하는 대조쌍

**보충 기록**
표·그래프의 수치는 신규 사례에 사용하지 않음. PDF 제목 표기 MetSat/MetaOp와 메타데이터 표기 차이는 식별번호로 연결.

## EE-03 — Single-Event Effects Test Report Texas Instruments, OPA855 Low-Noise Operational Amplifier

저자: Kaitlyn L. Ryder, Jonathan D. Barth, Michael J. Campola, Matthew B. Joplin, Thomas A. Carstens, Richard J. Hare
발행: 2022 cover; report date 2023-04-12 / NASA Technical Memorandum
식별번호: NASA/TM-20230009783 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20230009783
원문 후보: https://ntrs.nasa.gov/api/citations/20230009783/downloads/OPA855_OpAmp_LBNL_20221111_SEE-TestReport_v3.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: FULLTEXT_SECTION_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: AOS_OPAMP_SEE_LBNL_2022
권장 사용: P2 / TRAIN_CANDIDATE

**학습 목표 — DoriLab 설계 제안**
SEL 전원전류와 SET 출력 파형의 관측 경로를 분리한다; 시험 무관측을 다른 고장모드의 무발생과 구분한다

**읽을 부분**
PDF7쪽 §6~8 본문, 시험 목적은 PDF5쪽; 표의 수치로 임무율을 계산하지 않음

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
전류만 관측한 사례와 전류·출력 파형을 함께 관측한 사례를 비교

**보충 기록**
시험2022-11-11, 보고서 날짜2023-04-12. OPA847/856 등 같은 빔 캠페인 자료는 동일 누수 그룹 검토.

## EE-04 — System-Level Single Event Effects Test Report - PIRT1280MVCam InGaAs Infrared Camera

저자: Landen D. Ryder, Jean-Marie Lauenstein, Michael J. Campola
발행: 2024 / Technical report
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20250006620
원문 후보: https://ntrs.nasa.gov/api/citations/20250006620/downloads/COTS_InGaAs_SEE_TestReport_TM.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: PIRT1280MV_CAMERA_NSRL_SEE
권장 사용: P2 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
부품시험과 박스 수준 시험의 관측범위를 구분한다; 시스템 오류·복구·파괴적 영향의 시험 범위를 확인한다

**읽을 부분**
평가 담당이 시험체 하우징·빔·감시·오류 분류를 원문 검토

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
새 시스템 시험에서 모드별 증거가 충분한지 검토

## MAT-01 — Outgassing data for selecting spacecraft materials

저자: William A. Campbell Jr., Richard S. Marriott, John J. Park
발행: 1984 / NASA Reference Publication
식별번호: NASA-RP-1124 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20030053424
원문 후보: https://ntrs.nasa.gov/api/citations/20030053424/downloads/20030053424.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: NASA_OUTGASSING_DATABASE_RP1124
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
질량손실과 응축성 방출물 지표의 의미를 구분한다; lot·전처리·시험조건을 재료 데이터 재사용 조건에 연결한다

**읽을 부분**
시험 방법·시편 전처리·데이터 해석 서문, 선택한 재료 행은 원문 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
시험조건이 다른 재료값을 동일 성능으로 취급하는 사례 검토

**보충 기록**
당시 ASTM 방법·조건은 역사적 시험 정보. 후속 database 판본과 동일 재료lot 중복 분리 필요.

## MAT-02 — Evaluation of Oxygen Interactions with Materials 3: Mission and induced environments

저자: Steven L. Koontz, Lubert J. Leger, Steven L. Rickman, Charles L. Hakes, David T. Bui, Donald Hunton, Jon B. Cross
발행: 1995 / Conference paper
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/19950021210
원문 후보: https://ntrs.nasa.gov/api/citations/19950021210/downloads/19950021210.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: EOIM3_STS46
권장 사용: P2 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
열이력·UV·AO 노출·오염을 함께 확인한다; 서로 다른 노출량 추정 경로의 의미를 검토한다

**읽을 부분**
독립 담당이 비행 환경 정의와 노출량 추정·표면분석 절을 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
재료 반응 차이를 재료 자체에만 귀속하는 결론의 평가

## MAT-03 — Effect of Simulant Type on the Absorptance and Emittance of Dusted Thermal Control Surfaces in a Simulated Lunar Environment

저자: James R. Gaier
발행: 2010 / NASA Technical Memorandum
식별번호: NASA/TM-2010-216786; AIAA-2010-6111 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20100033112
원문 후보: https://ntrs.nasa.gov/api/citations/20100033112/downloads/20100033112.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: GRC_LUNAR_DUST_THERMAL
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
먼지 종류와 표면재료의 상호작용을 확인한다; 서로 다른 모사재의 열적 결과를 재사용할 때 조건을 점검한다

**읽을 부분**
시험 재료·먼지 특성·열광학 평가절을 원문 확보 후 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
먼지 부하량만 같고 종류가 다른 실험의 비교 가능성 판단

**보충 기록**
Thermal secondary; 수치·그리스문자는 원본 확인 후 전사. 기존 작업명은 The Effects of Lunar Dust on the Thermal Performance of Spacecraft Materials: Effect of Dust Type. 이번 등록 제목은 NTRS의 2026-09-14 확인 표기를 따르고 식별번호는 동일하게 유지.

## MAT-04 — Tutorial on Atomic Oxygen Effects and Contamination

저자: Sharon K. Miller
발행: 2017 / Conference paper / tutorial
식별번호: GRC-E-DAA-TN42180 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20170006623
원문 후보: https://ntrs.nasa.gov/api/citations/20170006623/downloads/20170006623.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: GRC_AO_TUTORIAL_2017
권장 사용: P2 / REFERENCE_ONLY

**학습 목표 — DoriLab 설계 제안**
AO 손상과 오염 경로의 기초 용어를 정리한다

**읽을 부분**
튜토리얼 원문에서 메커니즘·시험 대표성·재료 대응 부분

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
용어·원리 RAG 카드 작성, 실제 시험 결과 라벨과 분리

## FL-01 — Performance of all-metal demountable cryogenic seals at superfluid helium temperatures

저자: Louis J. Salerno, Alan L. Spivak, Peter Kittel
발행: 1989 / NASA Technical Memorandum
식별번호: NASA-TM-102190; AIAA-89-1728 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/19890013479
원문 후보: https://ntrs.nasa.gov/api/citations/19890013479/downloads/19890013479.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: AMES_CRYOGENIC_DEMOUNTABLE_SEALS
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
검출한계 이하와 누설률0을 구분한다; 온도·조립·반복노출의 범위를 보존한다

**읽을 부분**
시험치구·열사이클·누설 검출법·결론 원문 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
검출한계와 실제 누설률의 혼동을 고치는 판단 예제

## FL-02 — Thin-metal lined PRD 49-III composite vessels

저자: J. T. Hoggatt
발행: 1974 / Contractor Report
식별번호: NASA-CR-134555 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/19740011430
원문 후보: https://ntrs.nasa.gov/api/citations/19740011430/downloads/19740011430.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: PRD49_THIN_LINER_VESSELS
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
burst와 반복압력·liner 누설의 검증 목적을 구분한다; 제조상태와 실험 산포를 확인한다

**읽을 부분**
제작·시험 종류·liner 파손/누설의 본문 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
단발 강도 증거로 반복수명까지 결론내는 적용범위 검토

**보충 기록**
역사적 재료·제조조건 사례; 현재 허용압력·시험 안전절차는 별도.

## FL-03 — The Capillary Flow Experiments Aboard the International Space Station: Increments 9-15

저자: Ryan M. Jenson, Mark M. Weislogel, Noel T. Tavan, Yongkang Chen, Ben Semerjian, Charles T. Bunnell, Steven H. Collicott, Jorg Klatte, Michael E. Dreyer
발행: 2009 / Contractor Report
식별번호: NASA/CR-2009-215586 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20090040689
원문 후보: https://ntrs.nasa.gov/api/citations/20090040689/downloads/20090040689.pdf

권리 표기: NOT_CONFIRMED
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: ISS_CAPILLARY_FLOW_CFE
권장 사용: P2 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
중력조건과 접촉선·기하의 대표성을 구분한다; 영상 기반 실험과 모델 비교의 근거를 확인한다

**읽을 부분**
저작권 확인 후 평가 담당이 executive summary·실험절·영상 데이터 처리 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
지상 결과의 우주 모세관 현상 재사용 범위 평가

**보충 기록**
검색 메타데이터에서 권리문구 미확인. 제목9–15와 초록의 실제운용9–16 표기 차이 보존.

## FL-04 — Brush seals for cryogenic applications

저자: Margaret P. Proctor
발행: 1993 / Other (NTRS classification)
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/19940018590
원문 후보: https://ntrs.nasa.gov/api/citations/19940018590/downloads/19940018590.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: LEWIS_CRYOGENIC_BRUSH_SEALS
권장 사용: P2 / DEV_RESERVED

**학습 목표 — DoriLab 설계 제안**
치구·유체·온도별 seal 성능의 비교 전제를 확인한다

**읽을 부분**
Penn State/NASA 연구보고서 수록 원문 확보, 형상·운용조건·측정방법 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
같은 seal 이름이더라도 다른 조건의 데이터를 섞는 사례 검토

**보충 기록**
후속1994 viewgraph 등 동일 시험 캠페인 자료는 독립 평가로 분할하지 않음.

## SW-01 — NASA Operational Simulator for SmallSats (NOS3): Design Reference Mission

저자: John P. Lucas, Matthew D. Grubb, Justin R. Morris, Mark D. Suder, Scott A. Zemerick
발행: 2023 conference / Conference paper
식별번호: SSC23-XIII-06 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20230010613
원문 후보: https://ntrs.nasa.gov/api/citations/20230010613/downloads/SSC23%20NOS3%20Design%20Reference%20Mission.pdf

권리 표기: Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: NOS3_DRM_FRAMEWORK
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
컴포넌트 모사와 실제 장치 검증범위를 구분한다; 시험 oracle과 인터페이스 전제를 정리한다

**읽을 부분**
본문 framework·design reference mission·use-case 및 제한사항 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
SIL에서 확인된 기능과 HIL/실기에서 남은 근거를 분리

## SW-02 — The SDO FlatSat

저자: David L. Amason
발행: 2008 / Conference paper
식별번호: 해당 없음 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20080023611
원문 후보: https://ntrs.nasa.gov/api/citations/20080023611/downloads/20080023611.pdf

권리 표기: Work of the US Gov. Public Use Permitted.
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: SDO_FLATSAT
권장 사용: P2 / TRAIN_RESERVED

**학습 목표 — DoriLab 설계 제안**
전기 기능적 고충실도와 실제 비행환경의 차이를 찾는다; 검증하려는 구성과 시험대 구성을 연결한다

**읽을 부분**
구성·FSW acceptance·운용검증 절의 본문 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
FSW 기능검증에서 환경·타이밍 조건의 재사용 가능성 판단

## SW-03 — Radiation Hardening by Software Techniques on FPGAs: Flight Experiment Evaluation and Results

저자: Andrew G. Schmidt, Thomas Flatley
발행: 2017 / Conference paper
식별번호: GSFC-E-DAA-TN37055 / DOI: 등록하지 않음

공식 출처: https://ntrs.nasa.gov/citations/20170002014
원문 후보: https://ntrs.nasa.gov/api/citations/20170002014/downloads/20170002014.pdf

권리 표기: NOT_CONFIRMED
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: SPACECUBE_RHBSW_STPH4
권장 사용: P2 / DEV_RESERVED

**학습 목표 — DoriLab 설계 제안**
오류 주입·레이저 시험·비행 모니터링의 관측 대상을 구분한다; 무고장 관측기간과 복구 검증 근거를 분리한다

**읽을 부분**
권리 확인 후 implementation·fault emulation·flight observation 절 읽기

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
오류가 발생하지 않은 운용 결과를 오류복구 성공과 혼동하는 예제

**보충 기록**
공개배포 표시는 확인, 재사용 권리 문구는 미확인. SpaceCube1.0/2.0 계열 관계를 평가 분할에서 점검.

## SW-04 — Real-time Testing of Satellite Attitude Control With a Reaction Wheel Hardware-In-the-Loop Platform

저자: Morokot Sakal, George Nehma, Camilo Riano-Rios, Madhur Tiwari
발행: 2025 / arXiv preprint / conference contribution
식별번호: 해당 없음 / DOI: 10.48550/arXiv.2508.19164

공식 출처: https://arxiv.org/abs/2508.19164
원문 후보: https://arxiv.org/pdf/2508.19164

권리 표기: CC BY 4.0
확인 수준: CATALOG_ABSTRACT_CHECKED; 원문 파일 SHA-256: 아직 없음
시험·연구 그룹: SAT_ADCS_REACTION_WHEEL_HIL_2025
권장 사용: P2 / EVAL_RESERVED

**학습 목표 — DoriLab 설계 제안**
실제 구동기·시뮬레이터·CAN/제어기의 경계를 구분한다; 주입한 고장의 정의와 실제 고장 대표성을 검토한다

**읽을 부분**
평가 담당이 플랫폼 구성·인공 고장·limitations 절을 확인

**사례로 변환할 질문 — 아직 작성되지 않은 항목은 제안이다**
미사용 HIL 체계의 모델-하드웨어 경계조건과 주장 범위를 평가

**보충 기록**
arXiv v1, 15 pages. license 링크 CC BY4.0 확인; 상세 수치·그림은 후속 검토.
