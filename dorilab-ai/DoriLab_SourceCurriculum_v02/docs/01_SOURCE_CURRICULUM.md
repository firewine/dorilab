# DoriLab Engineering Source Curriculum
## v0.2 · 2026-09-14 · 학습 설계 및 출처 선정본

**6개 공학 영역 / 27개 선정 자료 / 40개 학습 후보 / 기존 32개 사례 보존**

이 문서는 우주 시험 문헌을 수집하는 목록이 아니라, 어떤 판단을 어떤 근거에서 학습하고 어떤 시험으로 확인할지 정하는 커리큘럼이다. 기존 DoriLab Rev.2.0의 BM 1, Domain Pack, 근거·형상·Scope 관리와 독립 평가 방향을 유지한다. [내부 기준: DoriLab 통합개발계획 Rev.2.0, 3·5·6·10·19·21장]

### 이번 결론

모델은 당분간 **Qwen3.5-2B backbone 하나와 공통 LoRA 하나**로 유지한다. 자료는 Mechanics, Thermal, EEE, Materials, Fluid/Pressure, Software/HIL로 나누되, 모델이 배우는 공통 판단은 증거의 충분성·측정의 의미·경계조건·적용범위·다음 활동이다. 분야별 모델 분리는 실제 평가에서 학습 간섭이 반복될 때의 선택지다.

5주 목표는 여섯 분야 전체의 전문가 모델이 아니다. **열·기계·기초 전기전자에서 출처가 추적되는 검토 업무 하나를 실제로 처리하고, 다른 분야로 확장할 수 있는 데이터·평가 경로를 만드는 것**이다.

### 이번 패키지의 실제 완성 범위

| 항목 | 현재 상태 |
|---|---|
| 기존 Apollo / Wijker 문헌과 32개 사례 | 원본 파일과 ID·정답 후보를 보존 |
| 신규 EEE 사례 | EMI/EMC와 SEE 보고서에서 4쌍·8개 후보 추가 |
| 27개 출처 | 서지·유형·권리표시·연구그룹·읽을 부분·학습과제 등록 |
| 원문 검토 수준 | 본문 확인과 서지·초록 확인을 자료별로 구분 |
| 사람의 정답 승인 | 아직 0개. 40개 모두 PENDING |
| 원본 PDF | 이번 ZIP에 미포함. 다운로드 도구와 파일 해시 기록 제공 |
| 실행 코드 | CPU 테스트 완료. 신규 GPU 학습 경로는 사용자 PC의 5-step 확인 대상 |

기존 v0.1의 Dev 20/20은 정형 실행계약 회귀 결과다. 이번 문헌 기반 후보는 다른 입력과 출력 계약을 사용하는 다음 실험이다. 두 점수를 하나의 추세선으로 연결하지 않고 각각 기록한다.

### 읽는 순서

1~3절에서 분류와 확장 규칙을 정한다. 4~9절에서 각 분야의 출처를 선택한다. 10~13절에서 사례 작성·분할·평가·5주 작업을 적용한다. 실제 명령은 별도 문서 **02_TRAINING_TUTORIAL.md / DOCX**를 따른다.

<!-- PAGE -->
## 1. 분류는 지식영역, 시험종류, 판단행동을 함께 사용한다

한 문헌을 폴더 하나에만 넣으면 복합 시험을 설명하기 어렵다. 기본 영역 하나와 보조 영역 여러 개를 기록하고, 시험 프로그램 식별자는 하나로 유지한다. 예를 들어 Swift BAT LHP는 Thermal이 기본이고 Fluid/Pressure가 보조다. 자료를 양쪽 폴더로 복제해 독립 사례처럼 세지 않는다. [TH-05]

| 축 | 예 | 용도 |
|---|---|---|
| 공학 영역 | MECHANICS, THERMAL, EEE | 담당 지식과 평가 결과 묶음 |
| 하위 영역 | RANDOM_VIBRATION, THERMAL_BALANCE, EMI_EMC | 해당 물리·시험의 개념 |
| 검증 단계 | Characterization, Qualification, Acceptance | 시험목적과 증거의 역할 |
| 제품·시험 수준 | Coupon, Component, Subsystem, System | 실제 시험대상의 수준 |
| 판단 개념 | 측정 대응, 경계조건, 원인 구분, 증거 충분성 | 분야 간 전이 평가 |
| 실행 행동 | 조회, 계산, 검토 이견, 자료 요청, 수정 불필요 | 모델·도구가 할 일 |

**시험종류와 검증 단계는 별개 필드다.** Random vibration은 시험종류이고 Qualification은 단계/목적이다. 동일 시험종류라도 제품 수준·형상·입력조건·승인 범위가 다르면 증거 사용범위가 달라진다. 이는 DoriLab 기존 Claim 구조에 맞춘 데이터 설계다. [내부 기준: Rev.2.0 6장]

## 2. 공통 코어와 역할은 유지한다

자료 에이전트는 문서·측정의 의미를 추출하고, 분석 에이전트는 실제 계산을 실행하는 도구와 연결하며, 검토 에이전트는 근거와 제안의 범위를 비교한다. 분야 태그는 담당 근거를 찾기 위한 정보이지 정답 행동을 정해주는 라벨이 아니다.

공통 학습 질문은 여섯 가지다. **무엇을 관측했는가 / 무엇과 비교할 수 있는가 / 어떤 조건에 적용되는가 / 무엇이 아직 불확실한가 / 어떤 추가 작업이 필요한가 / 이번 검토는 어디까지 끝났는가.** 새로운 분야에서도 같은 질문을 쓰되 필요한 물리 증거는 달라진다.

## 3. 출처 확인과 학습 준비를 분리한다

| 등록 상태 | 의미 | 다음 작업 |
|---|---|---|
| CATALOG_ABSTRACT_CHECKED | 서지와 초록 확인 | 본문 취득, 근거 절·페이지 확인 |
| FULLTEXT_SECTION_CHECKED | 실제 사용하는 본문 절 확인 | 사례·정답의 공학 검토 |
| LEGACY_BODY_CHECKED | 이전 패키지의 본문 확인 이력 승계 | 기존 사례와 원문 재검토 |


용도는 학습 후보·추가 읽기·개발평가·독립평가 예약으로 구분한다. 예약은 데이터 완성을 뜻하지 않는다. 자료의 공개 열람 가능성과 재사용 권리 표시는 별도로 관리한다. NASA NTRS에서도 문헌마다 표시가 다르다. CC BY 4.0 자료는 출처·라이선스·변경 사실을 함께 기록한다. [권리 참고: SOURCE_REGISTER.md; Creative Commons BY 4.0]

<!-- PAGE -->
## 4. Mechanics & Dynamics — 6개 자료

현재 힘 제한 진동을 시작점으로 **구조하중 → 모달/랜덤진동 → 계측 이상 → 전개기구**로 확장한다. 이 순서는 DoriLab의 SC-03과 후속 전개기구 검토를 연결하기 위한 제안이다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| VB-X1 / P0 · 후보 있음 | Force limited random vibration testing… (2015) | 지지구조 임피던스와 시험품 응답을 구분한다 |
| VB-03 / P1 · 학습용 읽기 | CoNNeCT SCAN Testbed: Semi-Empirical Force-Limiting Approach (2012) | 계산한 force limit와 실제 시험 응답을 연결한다 |
| MEC-03 / P1 · 학습용 읽기 | HGAS Deployment Mechanism: Integration, Characterization, Lessons Learned (2014) | 중력 보상장치의 영향을 제품 거동과 분리한다 |
| MEC-04 / P2 · 참고 문서 | NESC TB 15-02: Best Practices for Use of Sine Burst Testing (2015) | 정적하중 검증 대안으로 사용하는 sine burst의 적용 전제를 찾는다 |
| VB-S1 / P1 · 평가 예약 | E-STA Building Block Test Approach and Model Correlation (2019) | 부분조립체와 시스템 모델의 검증 계층을 구분한다 |
| MEC-06 / P2 · 개발평가용 | De-Trending Techniques: Cleaning Questionable Shock Data (2010) | 센서 영점이동과 물리적 충격응답을 구분한다 |

표의 긴 제목 일부는 축약했다. 전체 제목·저자·원문은 SOURCE_REGISTER.md를 따른다.

### 학습 단위

첫 번째 축은 입력·응답·경계조건의 구분이다. Wijker는 시험품과 지지구조의 동적 특성을 이용한 힘 제한 방법을 설명하고, CoNNeCT는 특정 시험 프로그램의 적용 사례다. 같은 원리를 다루어도 방법 정의와 실제 시험 결과는 다른 종류의 근거다. [VB-X1, VB-03]

두 번째 축은 시험장치 영향과 제품 이상을 구분하는 것이다. GPM HGAS 사례는 중력 보상장치와 전개기구의 상호작용을 포함한다. Shock 자료는 신호 보정과 재시험 판단을 다루는 후속 후보다. [MEC-03, MEC-06]

### 다음 데이터와 도구

모달 시험에는 주파수만 아니라 모드 대응·센서·지지조건 정보가 필요하다. 실제 계산 도구 후보는 PSD 적분/RMS, 시간구간 품질검사, FRF·모드 대응 지표다. 문헌 수치나 합성 데이터로 계산 검증을 할 때는 실제 계측 기록과 분리한다.

### 아직 빈 영역

접촉·체결·마찰수명, 구조좌굴·피로, acoustic, pyroshock의 충분한 본문 corpus는 아직 없다. 이번 6개 자료가 Mechanics 전체를 덮는 것은 아니다. 고객 사례가 들어오면 해당 하위 영역부터 추가한다.

<!-- PAGE -->
## 5. Thermal & Thermo-fluid — 5개 자료

**복합 열전달 → 열평형과 과도상태 → 모델 상관 → 열유체 기동** 순서로 읽는다. TVAC라는 챔버 이름보다, 해당 실험이 확인하는 물리량과 운용 상태를 먼저 구분한다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| TH-01 / P0 · 후보 있음 | Apollo Telescope Mount Thermal Systems Unit Thermal Vacuum Test (1971 catalogue / 1972 PDF) | 측정 위치와 모델 노드의 물리량을 연결한다 |
| TH-03 / P1 · 학습용 읽기 | A Physics-Based Temperature Stabilization Criterion for Thermal Testing (2009) | 온도 변화율과 잔여 과도응답의 관계를 검토한다 |
| TH-D1 / P1 · 개발평가용 | Transient thermal parameters correlation of spacecraft thermal models against test results (2022) | 전도·복사·열관성 파라미터의 식별 조건을 검토한다 |
| TH-S1 / P1 · 평가 예약 | Thermal Testing and Model Correlation of the Magnetospheric Multiscale (MMS) Observatories (2015) | 고온·저온·생존·과도 상태별로 증거를 분리한다 |
| TH-05 / P2 · 학습용 읽기 | Thermal Vacuum Testing of a Novel Loop Heat Pipe Design for the Swift BAT Instrument (2003) | 기동·부하·열싱크 조건에 따른 검증범위를 구분한다 |

### 기존 Apollo 사례를 사용하는 방법

TH-01의 16개 사례는 시험용 모사체, 배경복사, 열용량, 전력 소산, 노드별 평형, 센서 위치, 시험장치 차폐 등을 검토한다. 원문 사실과 합성 관측을 구분하는 기존 ID와 정답은 보존했다. [TH-01; legacy/PhysicsSeed32_v01/data]

열안정화 자료는 온도 변화율만 아니라 시험체의 물리특성과 잔여 과도상태를 검토하는 읽기 과제다. Transient correlation 자료에서는 어떤 관측이 어떤 파라미터를 식별하는지와 시험별 정보량을 정리한다. [TH-03, TH-D1]

### 다음 데이터와 도구

온도 이력의 안정화 지표, 전력·열수지, 측정 위치-모델 노드 매핑, 보정·검증 데이터 분리표를 도구와 연결한다. 실제 thermal-network solver를 추가할 때는 모델의 목적·입력범위·수치 검증을 별도로 관리한다.

### 아직 빈 영역

장기간 열사이클 열화, 특정 MLI 시공 품질, 고온 열보호, OHP/2상유동의 광범위한 raw data는 확보하지 않았다. Swift BAT LHP는 열유체 확장에 사용할 대표 읽기 자료 한 편이지 전체 열유체 성능 데이터셋이 아니다.

<!-- PAGE -->
## 6. Electrical & Electronics — 4개 자료

**전원-부하 조건 → EMI/EMC 기능 감시 → 방사선 영향별 관측 경로 → 시스템 수준 오류**로 확장한다. 초기에는 낮은 수준의 문헌 검토·데이터 해석에 집중하고, 실제 고전압·조사시험 운전은 기존 전문 시험 절차와 분리한다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| EE-01 / P1 · 학습용 읽기 | Stability testing and analysis of a PMAD dc test bed for the Space Station Freedom (1992) | 정전력 부하의 입력 특성과 전원-부하 임피던스를 연결한다 |
| EE-02 / P1 · 후보 있음 | Integrated Advanced Microwave Sounding Unit-A (AMSU-A): Electromagnetic Interference and Electromagnetic Compatibility Test Report, MetSat/MetOp AMSU-A1 (1999) | 전후 baseline과 주입 시험 중 계측을 구별한다 |
| EE-03 / P2 · 후보 있음 | Single-Event Effects Test Report Texas Instruments, OPA855 Low-Noise Operational Amplifier (2022 cover; report date 2023-04-12) | SEL 전원전류와 SET 출력 파형의 관측 경로를 분리한다 |
| EE-04 / P2 · 평가 예약 | System-Level Single Event Effects Test Report - PIRT1280MVCam InGaAs Infrared Camera (2024) | 부품시험과 박스 수준 시험의 관측범위를 구분한다 |

### 이번에 추가한 8개 후보

EE-02에서 자극 주입 중 응답과 전후 baseline의 관계를 다루는 2쌍을 만들었다. 사후 정상 복귀가 시험 중 이상 관측을 대체하지 않는다는 검토와, 시간 대응을 확인할 자료의 충분성을 묻는다. 본문 위치는 PDF14쪽의 §1.6 Pass/Fail criteria다. 보고서의 개별 수치 한계는 복사하지 않았다. [EE-02]

EE-03에서 SEL 감시용 전원전류와 SET 감시용 출력 전압 파형을 구분하는 사례, 사건 개수와 노출·전기 구성 기록을 연결하는 사례를 2쌍 만들었다. PDF7쪽의 §6~8을 근거로 했으며 새로운 관측은 모두 합성이다. [EE-03]

### 다음 데이터와 도구

전압·전류·기능 로그 동기화, brownout/재기동 이벤트, continuity·contact resistance 추세, EMC 자극-응답 이력 비교를 우선한다. 범용 판정수치가 아니라 고객이 제공한 기준과 기록의 관계를 검토한다.

### 아직 빈 영역

Grounding/bonding, derating, 절연·HV/Paschen, TID와 DDD는 확장 위치만 정해졌고 이번 선정자료로 충분히 채워지지 않았다. SEE 보고서를 TID·DDD의 실측 근거로 옮기지 않고 별도 문헌과 평가를 추가한다.

<!-- PAGE -->
## 7. Materials & Environmental Effects — 4개 자료

**재료 데이터의 시험조건 → 우주 노출량 → 먼지·표면 상호작용 → 메커니즘 참고 지식**으로 구성한다. 재료 이름만 같다는 이유로 다른 lot·처리·노출조건의 결과를 묶지 않는 데이터 설계가 중심이다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| MAT-01 / P2 · 학습용 읽기 | Outgassing data for selecting spacecraft materials (1984) | 질량손실과 응축성 방출물 지표의 의미를 구분한다 |
| MAT-02 / P2 · 평가 예약 | Evaluation of Oxygen Interactions with Materials 3: Mission and induced environments (1995) | 열이력·UV·AO 노출·오염을 함께 확인한다 |
| MAT-03 / P2 · 학습용 읽기 | Effect of Simulant Type on the Absorptance and Emittance of Dusted Thermal Control Surfaces in a Simulated Lunar Environment (2010) | 먼지 종류와 표면재료의 상호작용을 확인한다 |
| MAT-04 / P2 · 참고 문서 | Tutorial on Atomic Oxygen Effects and Contamination (2017) | AO 손상과 오염 경로의 기초 용어를 정리한다 |

### 학습 목표

NASA-RP-1124는 outgassing 지표와 재료 선택의 역사적 데이터 출처다. 수록 시험 방법·온도·전처리를 함께 읽고, 기록된 값과 현재 프로그램의 요구를 구분한다. [MAT-01]

EOIM-3는 재료 반응의 해석에 노출 환경을 함께 정의하는 자료다. 이 문헌은 독립 평가 후보로 예약한다. Lunar dust 자료는 같은 표면이라도 먼지 종류가 바뀌면 비교 조건이 달라질 수 있음을 검토하는 교차영역 과제로 둔다. [MAT-02, MAT-03]

### 다음 데이터와 도구

재료 lot·표면처리 passport, 노출량과 광학/열적 변화의 정규화, witness specimen·blank·control 관계를 관리한다. 측정불확도와 같은 공통 개념은 모든 영역에서 재사용하되 측정량의 정의는 별도로 둔다.

### 아직 빈 영역

접착제 접합강도, 복합재 피로, 진공 마찰·윤활, 방사선 재료열화는 별도 source pack이 필요하다. 먼지/레골리스 문헌도 궤도 재료검증과 월면 운용을 구분해 태깅한다.

<!-- PAGE -->
## 8. Fluid / Pressure — 4개 자료

이번 분야는 **누설·극저온 seal → 압력용기의 반복 거동 → 미소중력 모세관 유동**으로 시작한다. 추진기관의 전체 연소·시동·고위험 운전까지 한 번에 확장하지 않는다. 향후 Propulsion 하위 Pack은 별도 전문가와 데이터가 확보될 때 추가한다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| FL-01 / P2 · 학습용 읽기 | Performance of all-metal demountable cryogenic seals at superfluid helium temperatures (1989) | 검출한계 이하와 누설률0을 구분한다 |
| FL-02 / P2 · 학습용 읽기 | Thin-metal lined PRD 49-III composite vessels (1974) | burst와 반복압력·liner 누설의 검증 목적을 구분한다 |
| FL-03 / P2 · 평가 예약 | The Capillary Flow Experiments Aboard the International Space Station: Increments 9-15 (2009) | 중력조건과 접촉선·기하의 대표성을 구분한다 |
| FL-04 / P2 · 개발평가용 | Brush seals for cryogenic applications (1993) | 치구·유체·온도별 seal 성능의 비교 전제를 확인한다 |

### 학습 목표

Cryogenic seal 자료는 시험 온도·반복 노출·검출 한계를 함께 읽는 과제로 사용한다. 얇은 liner 압력용기 자료에서는 단발 강도와 반복압력/누설의 검증 목적을 분리한다. 실제 수치는 본문을 확보하고 시험체 조건을 확인한 뒤에만 라벨의 근거로 사용한다. [FL-01, FL-02]

CFE 자료는 지상 유동과 미소중력에서의 계면 거동, 영상 측정과 모델의 관계를 다루는 평가 후보다. 현재 검색 메타데이터에서 재사용 권리 문구를 확인하지 못해 권리 검토가 먼저다. [FL-03]

### 다음 데이터와 도구

누설률 단위 변환, 압력·온도 동기 기록, 배경 신호·검출한계, 반복 cycle과 시편의 연결, 영상 기반 계면 위치의 추출 방법을 분리해 관리한다.

### 아직 빈 영역

Cold-flow injector, cavitation, 밸브 유량맵, 펌프·압축기 2상유동, hot-fire 연소안정성은 포함되지 않았다. 커리큘럼에 자리만 두고 실제 시험 지식과 운영 권한을 확보할 때 확장한다.

<!-- PAGE -->
## 9. Software / Avionics / HIL — 4개 자료

**소프트웨어 모사 → 실제 인터페이스가 있는 FlatSat → fault injection와 복구 → 하드웨어가 닫힌 제어 루프** 순서다. 성공 로그 한 줄보다 어떤 fault·시간·관측 채널을 시험했는지가 중요하도록 사례를 설계한다.

| ID / 배정 | 선정 문헌 | 읽기의 초점 |
|---|---|---|
| SW-01 / P2 · 학습용 읽기 | NASA Operational Simulator for SmallSats (NOS3): Design Reference Mission (2023 conference) | 컴포넌트 모사와 실제 장치 검증범위를 구분한다 |
| SW-02 / P2 · 학습용 읽기 | The SDO FlatSat (2008) | 전기 기능적 고충실도와 실제 비행환경의 차이를 찾는다 |
| SW-03 / P2 · 개발평가용 | Radiation Hardening by Software Techniques on FPGAs: Flight Experiment Evaluation and Results (2017) | 오류 주입·레이저 시험·비행 모니터링의 관측 대상을 구분한다 |
| SW-04 / P2 · 평가 예약 | Real-time Testing of Satellite Attitude Control With a Reaction Wheel Hardware-In-the-Loop Platform (2025) | 실제 구동기·시뮬레이터·CAN/제어기의 경계를 구분한다 |

### 학습 목표

NOS3 자료는 컴포넌트 기반 모사와 design reference mission을 소개한다. SDO FlatSat 자료는 FSW·운용 검증을 위해 실제 전기 기능적 체계를 구성하는 사례다. 두 자료를 같은 충실도 수준으로 취급하지 않고 각 시험이 확인한 범위를 정리한다. [SW-01, SW-02]

RHBSW 자료는 fault emulation, laser injection, 비행 관측을 연결한다. Reaction-wheel HIL 자료는 실제 모터·드라이버·CAN·제어기·위성 모사를 결합한 시험 플랫폼이다. 이들을 통해 모사한 고장과 실제 고장의 대표성을 평가하는 사례를 설계한다. [SW-03, SW-04]

### 다음 데이터와 도구

시간 제한이 있는 상태전이 검사, 명령-telemetry 대응, fault injection 시점·복구상태·watchdog 기록, 반복 실행을 위한 test oracle을 도구로 분리한다. 시스템의 실제 시간 제약은 측정값으로 넣는다.

### 아직 빈 영역

독립 소프트웨어 보증, FPGA timing 검증, secure update, 네트워크·저장 무결성, 분산 복구의 전 범위를 이번 자료가 제공하지는 않는다. 고객의 실제 요구와 test vector를 우선 연결한다.

<!-- PAGE -->
## 10. 문헌을 학습 데이터로 바꾸는 작업 순서

**Source → Fact → Case pair → Review → SFT build → Evaluation → Runtime episode**로 이동한다. 원문을 읽는 일과 라벨을 만드는 일을 한 번에 합치지 않는다.

| 단계 | 작성할 것 | 완료 증거 |
|---|---|---|
| 출처 취득 | 서지·원문·권리·파일해시 | source registry와 다운로드 기록 |
| 근거 사실 | 원문 위치·자체 요약·가정·범위 | source_fact ID와 검토 위치 |
| 상황 구성 | 가상 관측과 검토할 제안 | SOURCE_DERIVED / SYNTHETIC 구분 |
| 대조쌍 | 근거 또는 제안 1~2개 변경 | 달라져야 하는 판단 이유 |
| 라벨 검토 | 가능한 행동·이유·요청 자료 | 엔지니어 검토자·날짜·수정 이력 |
| 학습 export | 승인된 쌍만 messages 형식으로 구성 | 데이터·프롬프트 해시와 분포 |
| 독립 평가 | 미사용 시험 프로그램·새 문서 형식 | 기준 답안·평가용 입력 분리 |

### source fact와 정답은 다르다

문헌에 ‘공급전류를 SEL 감시에, 출력파형을 SET 감시에 사용했다’고 적혀 있으면 그것은 출처 사실이다. ‘전류만 기록한 가상 사례에서 SET까지 검토했다고 제안했을 때 CHALLENGE한다’는 것은 그 사실과 DoriLab 정책을 결합한 라벨이다. 논문 저자가 해당 JSON 행동을 직접 정한 것으로 기록하지 않는다. [EE-03]

### 기존 32개와 신규 8개의 처리

기존 32개 원본은 변경하지 않았다. 새로운 대분류 태그는 `case_taxonomy_v02.json`에 따로 연결했다. 40개를 학습용으로 export할 때는 공용 physics-review-v0.2 프롬프트를 사용한다. 기존 정답의 의미는 보존하고 신규 EEE용 이유 코드 3개만 추가했다. 프롬프트·스키마 변경은 build manifest에 남는다.

### 사례 수는 작업 예산이다

40개 후보가 모두 승인되면 기존 Contract150과 합쳐 190개가 된다. 이것은 첫 실습 규모다. 이후에는 5~8개 실제 프로그램/방법 자료에서 검토한 Physics 사례 120~200개를 목표 작업량으로 잡는다. 같은 템플릿의 숫자 변형은 새 지식 한 건으로 계산하지 않는다. 분야별 목표 수량은 실험 결과에 따라 조정한다.

<!-- PAGE -->
## 11. 분할과 평가: 문헌 수보다 프로그램 독립성

같은 문헌의 문단 분리만으로는 독립성이 확보되지 않는다. 동일 시험품, 동일 계측 캠페인, 같은 결과의 후속 논문, 번역본, A/B 대조쌍을 묶은 그룹을 먼저 정한다. 이 그룹을 train/dev/eval 중 하나에 배정한다.

Wijker 논문은 JWST/MIRI와 ISS Linear Drive Unit 사례를 재분석한다. 같은 프로그램의 다른 논문을 평가에 넣을 때는 실제 데이터 공유 여부를 검토해야 한다. OPA855와 같은 빔 캠페인의 관련 부품 보고서, CFE 후속 논문도 동일하게 취급한다. [VB-X1, EE-03, FL-03]

**현재 EVAL_RESERVED는 평가 후보의 배정이며, 이미 밀봉된 시험문제가 있다는 뜻은 아니다.** 자료 목록과 주제는 공개돼 있다. 평가 작성자가 세부 사례·정답을 분리 관리하고 모델·프롬프트 동결 이후 평가한다. 결과를 확인해 다시 튜닝했다면 그 세트는 개발·회귀용으로 전환한다.

### 원문을 입력으로 주는 평가와 암기 평가

이 제품의 기본 평가는 새 문헌과 시험자료를 읽는 **open-book review**다. 평가 문헌의 원문을 모델의 reference_context에 주는 것은 작업의 일부다. 학습에는 평가 사례·정답·해설을 넣지 않고, 추론에는 현재 허용된 원문만 준다. 원문 접근이 없는 지식 회상 실험과는 별도 표로 기록한다.

### 비교군과 지표

| 비교군 | 묻는 질문 |
|---|---|
| Base 2B + 동일 근거·프롬프트 | 학습 전 수준은 어떤가 |
| Contract LoRA v0.1 + 동일 구성 | 실행계약 학습이 문헌 검토에 얼마나 전이되는가 |
| Contract + Physics LoRA v0.2 | 문헌 기반 사례 학습이 추가로 기여하는가 |
| 고정 규칙·도구 / 강한 모델 | 현실적인 대안보다 어떤 작업에서 유리한가 |

행동 정확도, strict JSON, 스키마·참조 유효성, 과도 경고, 누락, A/B 동시 정답률, 분야별 macro 결과를 분리한다. 적은 쌍에서의 백분율과 함께 분모·문헌 수·시험 프로그램 수도 제시한다. 현재 제공된 40개는 검토 공개 후보이며 독립 성능평가용이 아니다.

<!-- PAGE -->
## 12. 5주 실현 계획

기존 개발을 교체하는 일정이 아니라 문헌 기반 전문화 작업을 기존 LangGraph·보드 MVP에 넣는 일정이다. 전체 분량보다 실제 검토된 근거와 반복 가능한 처리경로를 완료 기준으로 둔다.

| 주차 | 학습·데이터 작업 | 실행·평가 작업 | 완료 산출물 |
|---|---|---|---|
| 1 | 기존 32개와 EEE8 검토, 원문·권리 확인 | 새 renderer/mask 5-step, 현재 모델의 후보 baseline | 승인 사례·manifest·초기 오류표 |
| 2 | TH-03·VB-03·MEC-03·EE-01 우선 본문 주석 | 동일 조건 Base/v0.1/v0.2 비교 | 첫 혼합 LoRA와 분야별 결과 |
| 3 | 정상/문제 대조쌍 보완, 필요한 교차분야 사례 작성 | 자료조회-계산-검토-보드 갱신 한 경로 | 실제 입력을 처리하는 Episode |
| 4 | 모델과 prompt 고정, 독립 평가 작성자 자료 인계 | 외부 프로그램, 정상·누락·Scope-limited 사례 평가 | 오류·검토시간·호출·토큰 비교 |
| 5 | 수정은 릴리스 구분, 데이터·코드 동결 | 새 자료 추가와 부분 재검토 시연 | 모델·재현 패키지·검토 결과 |

P2 분야는 병행 독서·출처 등록을 하되, 고객 사례가 없는 상태에서 모두 학습시키는 일을 선행조건으로 두지 않는다. 특정 영역을 추가해 기존 열·기계 성능이 떨어지면 학습 mix·정답 충돌·입력 계약을 먼저 점검한 후 전문 adapter 분리를 비교한다.

## 13. 다음 확장과 릴리스 기준

첫 릴리스는 단일 문헌을 읽는 판단에서 시작한다. 이후에는 온도·전원 로그, 진동·기능 reset, 압력·온도·누설처럼 두 영역의 기록을 하나의 Episode에서 다룬다. 이때 모든 부문을 한 번에 ‘통과’시키는 대신 검토 가능한 근거, 미확인 항목, 다음 작업을 보드에 각각 남긴다.

새 분야를 릴리스에 포함하는 기준은 **확인한 본문 출처, 검토한 정상/문제 사례, 기존 영역 회귀시험, 새로운 프로그램의 평가, 실행 예산과 사람 검토범위**다. 학습 단계 이름만 늘리는 것이 아니라 이를 뒷받침하는 기록이 남아야 한다.

### 남아 있는 작업과 확인 한계

27개 모두의 전문을 읽고 사례화한 상태는 아니다. 현재 실제 후보는 TH-01·VB-X1·EE-02·EE-03의 40개다. 그중 기존 두 출처는 이전 본문 검토 이력을 승계했고, 신규 EEE는 사용하는 본문 절을 확인했다. PDF 페이지 이미지 요청이 실패한 자료에서는 표·그림의 새 수치를 전사하지 않았다. FL-03과 SW-03은 메타데이터에서 재사용 권리 문구가 확인되지 않아 후속 확인 대상으로 둔다.

상세 서지·원문 주소·권리표시·시험그룹·읽기 과제는 **SOURCE_REGISTER.md / source_manifest_v02.json**에 있다. 27개 문헌마다 **templates/*_worksheet.md**가 제공된다.
