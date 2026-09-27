# 출처별 소스 커리큘럼

## 출처 선택 원칙

추가 학습은 공학 사실의 암기량보다 검토 대상, 적용 전제, 관측 가능량과 근거 관계의 구분에 초점을 둔다. 원문이 공개되어 있고 본문에 판단 경계가 명시된 자료를 우선했다. 발행연도가 최신이라는 이유만으로 채택하지 않았다.

기존 자료의 TH-01, VB-X1, EE-02, EE-03과 NS10의 RTG4/MRO/CM2는 회귀 자료로 유지한다. 새로운 TRAIN/DEV/RESERVED를 출처와 프로그램으로 나눴다. 전체 기존 저장소와 동의어/파생 논문 검사는 Codex 착수 작업이다. 겹치면 독립 평가로 사용하지 않는다.

## TRAIN: 48건 / 3개 출처

### SR13-TIRS / 열시험과 상관

**Lessons Learned during Instrument Testing for the Thermal Infrared Sensor (TIRS)**. Peabody, Otero, Neuberger. 2013 학회 논문. NTRS 식별자 20160000799.

원문: https://ntrs.nasa.gov/citations/20160000799

읽기: IV(4쪽), V.A~C(5~6쪽), VI(7쪽). 가족 네 개는 국소 온도와 평균, as-built 모델 대조, 사전 모델과 상관 후 모델 구분, 작은 복사 결합의 생략 검토다. 논문의 권고와 합성 사례의 별도 계산 기준을 구분한다.

### SR13-NEA / 기구와 열환경 연계

**Testing and Maturing a Mass Translating Mechanism for a Deep Space CubeSat**. Few, Lockett, Wilson, Boling, Loper. NTRS 20180005148.

원문: https://ntrs.nasa.gov/citations/20180005148

확인 범위는 3쪽 Executive Summary다. 완성된 최종 학회 논문 전체를 읽었다고 기록하지 않는다. 가족 네 개는 시험 종류의 범위, 하우징과 코일 측정량, 모터 회전과 실제 이송, 재설계 계획과 실제 검증 완료다. 2017년 당시 진행 중인 조사를 후속 성공으로 바꾸지 않는다.

### SR13-RHOBC / 전기와 시스템 복구

**Vorago RH-OBC-1 Single Event Effect Characterization Test Report**. Wilcox, Seidleck. 보고서 2020-08-06, 시험 2019-06-01.

원문: https://ntrs.nasa.gov/citations/20205006200

읽기: 1절(2쪽), 3.1절(3쪽), 6절(11쪽). 가족 네 개는 전원 제어 도달 범위, 부품별 원인 관측, 파괴와 기능 중단 구분, Boot FRAM와 MCU 복구 의존성이다. 실제 보고서의 수치 표는 학습 사례에 복제하지 않는다.

## DEV: 24건 / 3개 출처

| 출처 | 읽을 부분 | 검사할 기술 |
|---|---|---|
| HYPSO hyperspectral imager TVAC, CEAS Space Journal, DOI 10.1007/s12567-023-00501-3 | HTML 1~2절의 실험 범위와 계측 경로 | 검증 범위와 측정량 대응 |
| CANYVAL-C structural/thermal design, Aerospace 2021, DOI 10.3390/aerospace8060150 | 6절 및 진동/상관 본문 | 구속 변경과 고유진동수 해석 |
| PROBA-V SRAM SEE instrumentation, Electronics 2024, DOI 10.3390/electronics13101822 | 3.1, 4.1, 5절 | 시간 동기와 관측 누락 |

DEV는 prompt와 추론 구조 선택용이다. 결과를 보고 조정한 뒤 독립 test라고 부르지 않는다.

## RESERVED_TEST: 24건 / 3개 출처

OPS-SAT TVAC, ARAMIS composite battery tile modal analysis, 16 nm FinFET shift-register SEU 자료는 평가자 패키지로 분리했다. 제목과 DOI만 `reserved_inventory_metadata_only.json`에 있다. 구체적 사례, 근거 요약과 정답은 구현자가 읽지 않는다.

## 학습량의 해석

기본 TRAIN 48건은 12개 관련 가족이다. 관측을 유지한 제안 대조와, 질문을 유지한 입력 준비 대조를 포함한다. 반복 표본을 독립 관측으로 세지 않는다.

새로 만들 학습 export의 제안 구성은 기존 contract replay, 기존 physics의 검토된 고유 상태, 새 TRAIN이다. 이전 96행의 반복을 그대로 또 붙이기 전에 고유 상태를 세고 원자료를 보존한다. 예를 들어 기존 150 contract + 고유 physics 20 + 새 48이면 218행이다. 이는 서버에서 아직 확인하지 않은 구성 예시이며 확정 행 수가 아니다. 실제 ID 변형/시맨틱 중복 검토와 정확한 manifest를 먼저 만든다.

새 TRAIN/DEV/RESERVED 출처의 수치와 관측은 서로 교차 재사용하지 않는다. 공통 검토 기술의 교육은 허용하되 다른 split의 정답 해설을 요약해서 넣는 방식은 금지한다.
