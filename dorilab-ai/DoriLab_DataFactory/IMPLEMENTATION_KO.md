# DoriLab 논문→검토데이터→모델 자동화 구현안

작성일: 2026-09-20 · 설계 제안과 실제 제공 코드를 구분한 개발 기준서

## 0. 이번 결정

목표는 논문을 많이 내려받거나 JSON을 많이 만드는 일이 아니다. **새 논문에서 얻은 판단 사례를, 사람이 근거와 이유를 이해하며 검토할 수 있도록 만들고, 채택된 사례로만 모델을 반복 개선하는 것**이다.

기존 SourceCurriculum_v02의 자료·학습 코드는 보존한다. Source Factory(원문 취득·파싱), Case Factory(사실·사례·검토), Model Factory(데이터 빌드·학습·평가)를 연결한다. 공통 상태는 데이터베이스에 두고 LangGraph는 중단·재시도·다음 작업 실행에 사용한다.

첫 구현 우선순위는 **검토 화면과 사례 계약 → 배치 원문 처리 → 교사 모델 생성 → 학습 연결**이다. 읽을 수 없는 사례를 먼저 대량 생산하면 사람의 검토 병목도 함께 커진다.

### 현재 확인한 근거

- 사용자 캡처: `DoriLab_SourceCurriculum_v02/reports/DoriLab_v08_Review_Desk/REVIEW.html`. AP06-01 A/B에서 문제·결론·설명·평가 상태가 잘 구분되지 않는다.
- 제공 ZIP의 `data/physics_candidates40_v02.jsonl`에는 40개 후보가 있고, 원문 요약·가상 관측·정답 후보·한국어 이유가 분리돼 있다.
- `dcurr.review`, `dcurr.prepare`, `dcurr.train`, `dcurr.evaluate`가 이미 있다. 따라서 전체 학습 프로젝트를 교체할 이유는 없다.
- 실제 v08 HTML·생성 코드·실행 결과 파일은 이번에 확보하지 않았다. 화면에 보이는 항목과 제공된 v02 코드만 확인했다. 제공 프로토타입은 v08 파일을 수정하거나 그 결과를 자동 import하지 않는다.
- Engineering_Curriculum_v1은 별도 산출물이다. 두 패키지의 소스 수와 스키마를 자동 합치지 않는다. 현재 운영 중인 v02 경로를 기준으로 어댑터를 설계한다.

## 1. 검토 목적을 세 가지로 분리

### 1.1 공학 제안 검토

이 입력 범위에서 제안이 근거로 지지되는가? 반박되는가? 아니면 정보가 모자라는가?

- `SUPPORTED`: 제공 근거가 해당 제안을 뒷받침한다.
- `CONTRADICTED`: 제안이 제공 근거와 충돌한다.
- `INSUFFICIENT`: 양쪽을 결정할 핵심 근거가 없다.

이는 특정 claim의 판정이다. 시험품 전체의 합격·인증·운용 승인과 구분한다. 특히 `NO_ACTION_REQUIRED`는 해당 검토 작업의 추가 수정이 없다는 뜻이며 자동으로 제품 PASS로 변환하지 않는다.

### 1.2 학습 사례 검토

질문이 이해되는가, 원문 사실과 가상 조건이 구분되는가, 정답과 이유가 타당한가, 한 가지 합리적인 답만 존재하는가? 여러 다음 행동이 모두 합리적이면 허용 답 집합이나 최종 업무 조건으로 채점한다. 질문에 없는 작업 우선순위를 유일한 정답으로 강제하지 않는다.

### 1.3 학생 모델 평가

실제 모델의 결론·근거·다음 조치가 검토된 기준과 일치하는가? JSON 문법, 필수 필드, 허용 ID는 별도 기술 검사다. 기준 정답 설명을 모델의 실제 설명으로 채워 넣지 않는다. 기존 출력에 이유가 없으면 `모델 이유 미출력`으로 남긴다.

세 모드는 공유 화면을 쓸 수 있으나 저장 대상·버튼·상태를 분리한다. `PARTIAL`은 고정된 채점항목에서 계산할 수 있지만 UI가 독자적으로 새로운 Gold를 만들지 않는다.

## 2. 검토 카드가 먼저 만족할 계약

카드 첫 화면에는 다음 다섯 문장이 있어야 한다.

1. 질문: 무엇을 결정하는가?
2. 제안: 누구의 어떤 제안을 검토하는가?
3. 관측: 이 사례에서 판단을 바꾸는 실제 조건은 무엇인가?
4. 결론과 짧은 근거: 어떤 근거가 어떤 결론을 뒷받침하는가?
5. 다음 조치: 무엇을 유지·수정·추가 확인해야 하는가?

A/B에서는 바뀐 조건을 나란히 보여준다. A가 항상 나쁜 사례 또는 B가 항상 좋은 사례가 되지 않게 만들며, 모델 입력에는 A/B 표시·정답 해설·작성자 메모를 보내지 않는다.

### J7 사례의 표시 예

- 공통 질문: J7을 T_case의 직접 측정값으로 사용해도 되는가?
- A의 조건: 같은 케이스 표면 위치와 가중치로 평균을 구성했다는 대응 근거가 있다.
- B의 조건: J7은 내부 히터, T_case는 케이스 평균이며 대응 관계가 없다.
- 기준 초안: A는 주어진 대응 정보가 해당 시험에 유효하다는 범위에서 제안 지지. B는 직접 대응 제안에 이견.
- 모델 실제 출력: A는 NO_ACTION_REQUIRED, B는 CHALLENGE. 화면의 원래 reason은 그대로 보존한다.
- 모델 실제 설명: 캡처에는 없음. 기준 초안의 한국어 해설은 별도 영역에 표시한다.

A에 대한 판단은 측정 불확도, 시간 정렬, 센서 건전성 등 모든 항목을 확인했다는 뜻이 아니다. 범위를 확장하려면 추가 관측과 질문을 함께 추가한다.

### 블라인드 검토

질문·증거를 읽고 자신의 판단을 입력한 뒤 기준 초안을 열 수 있도록 한다. 처음에는 이 절차를 권장하고, 실제 독립 평가에서는 권한·API 수준으로 별도 평가자를 분리한다. HTML에서 숨기는 것만으로 sealed 데이터 보호가 완성되지는 않는다.

## 3. 전체 파이프라인

```text
분야별 검색 요청 / 기존 출처 등록부 / 사용자 원문 업로드
  → 후보 검색·중복 묶기
  → 원문 취득·사용 조건 확인
  → 페이지·표·그림·수식·단위 보존 파싱
  → 근거 사실 추출과 출처 연결
  → 검토 질문·제안·가상 상황·정답 후보 생성
  → 구조·근거·물리적 일관성·가독성·분할 검사
  → 독립 재검토 후보 + 사람 검토 큐
  → 승인된 데이터 스냅샷
  → 학습 작업 큐 → 이전/기본/후보 모델 비교
  → 배포 후보 검토
```

RAG 원문 저장소는 사례 생성과 별도로 유지한다. 논문이 들어왔다고 바로 재학습하지 않는다. **기존에 없던 판단 능력을 보강하는 검토된 사례 묶음이 준비됐을 때** 학습 빌드를 만든다.

## 4. 논문 수집 자동화

### 4.1 실제 연결 순서

1. 기존 27개 등록부의 URL과 원본부터 처리한다. 서지·초록 확인만 된 자료는 본문 취득 단계로 이동한다.
2. NASA STI/NTRS의 OpenAPI 및 공개 메타데이터를 연결한다. NASA는 OpenAPI를 권장 수집 경로로 안내하며 연도별 NDJSON도 제공한다.[R1]
3. Crossref에서 DOI·서지·링크·권리 메타데이터를 보충한다. Crossref는 원문 자체를 보관하는 곳이 아니라 메타데이터와 일부 원문 링크를 제공한다.[R2]
4. OpenAlex는 검색·주제·인용 연결을 통한 후보 확장에 사용한다.[R3]

초기에는 NASA+Crossref 두 어댑터로 충분하다. ESA·IEEE·출판사별 다운로드는 실제 사용조건과 API를 확인해 하나씩 추가한다. 수집 실패는 `FETCH_BLOCKED`로 기록하고 재시도를 제한한다. 로그인·유료 접근을 우회하지 않는다.

### 4.2 분야와 공통 판단 개념을 함께 검색

- MECHANICS: force-limited random vibration, modal correlation, fixture effects, deployment test.
- THERMAL: thermal balance correlation, sensor-model mapping, stabilization, parasitic heat.
- EEE: power transient, source-load impedance, EMC test setup, radiation observables.
- MATERIALS: outgassing, contamination, atomic oxygen, coating degradation.
- FLUID_PRESSURE: cryogenic leakage, pressure cycling, seal reuse, capillary flow.
- SOFTWARE_HIL: spacecraft HIL, fault injection, timing, FDIR, sensor simulation.

선정 우선순위는 인용수보다 현재 데이터의 빈칸을 기준으로 한다. 본문 접근 가능성, 실제 시험 구성, 경계조건, 계측, 실패·정상 비교, 한계 설명을 점검한다. 기존 소스와 같은 시험 캠페인이라면 독립 사례 수를 늘린 것으로 집계하지 않는다.

### 4.3 식별과 분할

`doi / ntrs_id / document_version / raw_sha256 / program_id / campaign_id`를 각각 보관한다. 정확한 중복 제거와 같은 시험 계열 묶기는 다른 작업이다. `program_id`의 자동 추정은 후보이며 사람이 확인한다. 한 사례가 Train·Eval 양쪽 계열의 여러 소스를 사용하면 그 사례를 격리하거나 전체 연결 집합을 재분할한다.

RAG 사용권, 파생 학습자료 사용권, 외부 교사 전송권, 재배포권을 따로 기록한다. `public`이나 `open access`만으로 모든 용도를 승인한 상태로 만들지 않는다. 이 설계에서의 권리 상태는 조직이 검토한 기록이지 법률 결론 자동화가 아니다.

## 5. PDF 처리와 출처 위치

첫째, 문서에 내장된 텍스트와 레이아웃을 먼저 사용한다. Docling은 구조화 문서에 페이지 번호·bbox·charspan과 표 구조를 보관할 수 있어 기본 파서 후보로 적합하다.[R4]

둘째, 표·수식·그림은 일반 문장 청크와 분리한다. 표는 행·열 이름, 단위, 각주, 시험 조건을 함께 저장한다. 그래프의 수치를 읽어야 하는 경우 해당 페이지 이미지와 축·범례·단위를 확인한 뒤 별도 검수한다.

셋째, 스캔 페이지처럼 텍스트가 없거나 깨진 경우에만 페이지 단위 OCR/비전 경로로 보낸다. 전체 PDF의 무조건 OCR은 기본 경로가 아니다.

넷째, PDF의 물리적 페이지 인덱스와 인쇄 페이지 표기를 둘 다 기록한다. 원문 인용, 원문 요약, 한국어 번역, 가상 사례를 필드로 구분한다. 기존 source_facts의 요약을 검색 가능한 원문 인용으로 잘못 표시하지 않는다.

원문이 바뀌면 자동 파생된 facts/cases/build 중 영향받는 항목을 찾고 `STALE_REVIEW`로 전환한다. 과거 사용 이력은 삭제하지 않는다.

## 6. 교사 모델은 세 번의 목적 있는 작업으로 사용

### Pass 1 — 원문 사실

입력은 원문 조각과 정확한 위치다. 출력은 시험체, 경계조건, 관측물리량, 분석 가정, 관측 결과, 저자의 제한사항이다. 없는 항목은 null로 둔다. 여기서는 정답 행동을 만들지 않는다.

### Pass 2 — 검토 사례와 설명

승인된 사실 또는 근거가 연결된 후보 사실에서 질문·제안·관측을 만든다. `source_derived`, `synthetic_counterfactual`을 분리한다. A/B 변경 필드와 결정에 미치는 영향을 함께 기록한다. 하나의 사실에서 유사한 사례를 수십 개 생성하기보다 서로 다른 판단 조건 2~3쌍부터 시작한다.

정답 후보는 결론만이 아니라 **2~4문장의 짧은 공학적 근거, 근거 ID 연결, 필요한 후속조치**를 갖는다. 비공개 사고과정이나 장문의 추론 독백을 수집하는 목적이 아니다.

### Pass 3 — 별도 검토

작성 모델의 정답을 먼저 보여주지 않고, 같은 질문과 근거로 다른 검토를 생성한다. 그 뒤 두 결과를 비교한다. 모델/프롬프트를 분리해도 오류의 통계적 독립성이 보장되는 것은 아니므로, 일치는 자동 정답 인증이 아니라 검토 우선순위 신호로 쓴다.

교사는 특정 모델명에 고정하지 않는다. provider/model_id/schema_version을 설정값으로 받으며, 실사용 모델의 지원 API·데이터 사용조건은 연결 시 확인한다. 학생의 작은 모델에 어려운 문헌 정답 생성까지 맡기지 않는다.

OpenAI의 Structured Outputs는 JSON Schema를 따르는 출력 형식을 만드는 데 유용하지만, 그 안의 의미 오류는 별도 검토 대상이다.[R5] 많은 오프라인 요청은 지원 모델의 Batch API로 묶을 수 있다.[R6] 비밀키는 환경변수에 두고, 예산·최대 출력·재시도 상한을 작업 단위로 설정한다.

## 7. 후보 품질 게이트

| 검사 | 담당 | 실패 시 경로 |
|---|---|---|
| JSON·필수 필드·ID 참조 | 코드 | 제한된 자동수정 또는 생성 재요청 |
| 인용문·페이지·표 위치 | 코드+선별 원문 확인 | source extraction 재검토 |
| 입력/응답/허용치·단위·sigma/PSD | 도구+공학 검토 | 조건·식 검토 큐 |
| 근거가 결론을 지지하는가 | 별도 모델+사람 | 이견 큐 |
| A/B 변화가 정답 변화의 이유인가 | 코드+공학 검토 | 사례 재작성 |
| 정답이 여러 개인가 | 사람+업무정책 | 허용답 집합/질문 구체화 |
| 사람이 문제를 이해할 수 있는가 | 한국어 카드 검사+검토 | 설명 보완 큐 |
| 같은 프로그램·중복·정답 노출 | 코드+그룹 검토 | 격리·분할 재검토 |

`SCHEMA_VALID`, `SOURCE_LINKED`, `SEMANTIC_REVIEWED`, `HUMAN_APPROVED`는 별도 상태다. 자동 검사 통과는 `AUTO_CHECKED_CANDIDATE`로 남긴다. 자동 통과 자료를 학습에 쓰는 실험은 별도의 `SILVER` 데이터셋으로 관리하고, 사람 검토 자료 `GOLD`와 효과를 비교한다.

검토 큐는 위험·분야 신규성·두 검토의 이견·근거 파싱 불확실성·학생의 실제 실패를 우선한다. 자동 통과 그룹에서도 무작위 표본을 확인해 놓친 오류율을 추정한다. 초기에는 새 원리·새 분야의 사례를 전수 검토하고, 검토가 누적된 변형만 샘플링 정책을 검토한다.

## 8. 프로그램 구조와 책임

```text
DoriLab_SourceCurriculum_v02/
  dcurr/                  # 기존 준비·학습·평가 코드 유지
  factory/
    sources/              # nasa, crossref, registry import
    parsing/              # 문서 구조와 페이지 evidence
    generation/           # facts, scenarios, explanations
    checks/               # schema, grounding, pairs, leakage
    workflow/             # LangGraph nodes/graphs, retries
    datasets/             # 승인집합 build, split registry
    training/             # 기존 dcurr.train subprocess 어댑터
    models/               # 교사·학생 호출 규격
    store/                # SQLite repository, immutable blobs
    api/                  # FastAPI routes
  ui/                     # 검토 데스크: HTML/JS부터 시작
  config/                 # taxonomy, tools, budgets, model profiles
  work/                   # raw/parsed/facts/cases/runs/manifests
```

공통 오케스트레이션은 LangGraph를 사용한다. 체크포인터는 실행 진행상태를, 공용 저장소는 원문·근거·검토 기록을 보관한다.[R7] 사람이 판단할 때 `interrupt()`로 멈추고 resume한다. 중단한 노드는 다시 실행될 수 있으므로 유료 호출·파일쓰기·보드반영에는 idempotency key를 붙인다.[R8]

### 두 실행 그래프

**SourceGraph**: import/discover → rights gate → fetch → parse → facts → facts check → source ready.

**CaseGraph**: choose skill gap → make cases → validators → independent reconstruction → readability → review queue → reviewed dataset build.

학습은 별도 GPU 큐에서 실행한다. Windows WSL의 RTX 5080 한 장에서는 학생 학습과 큰 교사 추론·대형 PDF 비전 파싱을 동시에 경쟁시키기보다 순차 예약한다. Mac은 문헌 검토 UI, 웹/API 개발, 일부 CPU 전처리에 사용한다. 먼저 WSL 단일 프로세스로 완성하고, 두 장비 분산 운영은 병목이 측정된 다음에 추가한다.

### API 초안

- `POST /sources/import`: 기존 등록부·URL·DOI 등록.
- `POST /jobs`: source 또는 case 작업 시작, budget와 config hash 포함.
- `GET /jobs/{id}`: 단계·실패·비용·재개 가능 여부.
- `GET /cases/{id}`: 질문·입력 근거만 반환.
- `POST /cases/{id}/reference`: 검토용 기준 공개, 열람 이벤트 기록.
- `POST /cases/{id}/review`: reviewer, case_hash, label_revision, verdict, 이유, 증거검토 상태 저장.
- `POST /datasets/build`: 승인집합 스냅샷 생성.
- `POST /training/jobs`: 명시한 dataset/config로 후보 학습.
- `POST /releases/propose`: 회귀 결과가 첨부된 승격 후보. 자동 고객 배포는 별도.

## 9. 반복 비용과 복구

`job_key = hash(source_revision + stage + input_hash + model_id + prompt_hash + schema_hash + tool_version)`를 기본으로 사용한다. 같은 작업이 이미 완료되면 저장 결과를 재사용한다. 생성 설정·seed·요청 ID·응답 ID도 기록한다. API 서버가 처리했는지 불확실한 timeout은 `UNKNOWN_REMOTE_STATUS`로 남겨 중복 과금을 피한다.

한 문서당 생성 횟수와 전체 배치의 비용 상한을 둔다. Parser 실패, 권리 미확인, 긴 입력, 잘린 모델 출력, 참조 없음 등을 구분해 큐로 보낸다. 자동수정 2회 같은 값은 초기 설정 예시이며 실제 오류 유형을 보고 조정한다.

작업 1,000개가 중간에 멈춰도 완성된 997개를 다시 만들지 않고 실패한 3개만 재실행하도록 하는 것이 핵심이다.

## 10. 학습·평가 자동화

1. 승인된 새 사례와 기존 분야 replay를 고정된 데이터 빌드로 만든다.
2. Prompt·Schema·Tokenization·EOS·labels·최대 길이·학습 가능한 파라미터를 preflight한다.
3. 작은 smoke 실행 후 본 학습을 GPU 큐에 넣는다.
4. 기본 모델, 이전 릴리스, 새 후보를 같은 질문·근거·도구로 비교한다.
5. 분야·정상/문제·읽을거리 길이·근거 가용성별 지표를 분리한다.
6. 릴리스 후보만 사람이 확인하고, 배포는 별도 승인으로 둔다.

기존 강점이 유지되는지 보는 L1 회귀, 문헌 복합 검토 L2, 실제 도구와 보드 변경을 포함한 L3를 분리한다. `wrong reason`, `missing evidence`, `false alarm`, `false acceptance`, `format failure`는 다른 실패다. 인용 ID가 존재한다는 사실만으로 인용이 결론을 뒷받침한다고 판정하지 않는다.

새 문헌이 모델 사전학습에도 없었다고 확인된 것은 아니다. 평가 기록에는 ‘우리 SFT에 사용하지 않은 시험 프로그램’이라고 범위를 명시한다. Dev 결과를 본 뒤 수정하면 Dev이며, sealed는 독립 작성·저장·평가 시점으로 보호한다.

RAG가 새 평가 논문 원문을 제공하는 것은 ‘문헌을 읽고 해석하는 평가’에서 합법적인 입력 설계다. 정답·작성자 해설·미래 사건은 입력에서 제외한다.

수집량, 승인 사례 수, 근거당 중복률, 엔지니어 수정시간, 무작위 재검토 오류율, 유효 사례당 비용, 모델의 미사용 프로그램 성능을 함께 측정한다. 학생이 어려워하는 부분은 다음 검색 우선순위로 사용하되 sealed 결과를 자동 active-learning 루프에 넣지 않는다.

## 11. 10작업일 우선 구축안

전담 개발자 1명과 분야 검토 시간 확보를 가정한 작업계획이며, 완료 보장 일정은 아니다. 외부 API·GPU 호환성 문제가 생기면 기존 학습 환경을 보존한 상태에서 어댑터를 격리한다.

| 작업일 | 핵심 작업 | 완료 증거 |
|---|---|---|
| 1–2 | 검토 카드·기준/모델 분리·기존 데이터 import | J7 같은 사례를 설명 없이 이해하고 판단 기록 가능 |
| 3–4 | 기존 소스 취득·NASA/Crossref 수집·문서 파싱 | 출처 5개가 페이지 근거로 연결, 차단·중복 재실행 테스트 |
| 5–6 | 사실→사례→별도 검토 교사 연결 | 2개 문헌에서 새 후보 배치와 읽을 수 있는 카드 생성 |
| 7–8 | 가독성·근거·A/B·split 검사와 검토 큐 | 정상 자동통과 그룹을 포함한 표본 재검토 결과 |
| 9–10 | 데이터 build→기존 학습→평가→보고서 | 한 명령의 추적 가능한 후보 학습·비교, 기존 모델 보존 |

첫 배치는 5개 문헌 정도로 제한하고 문헌마다 독립적인 판단 원리를 먼저 추출한다. 검토 가능한 사례 생산이 확인되면 20개, 100개 단위로 늘린다. 전 영역 동시 expansion보다 지금 약한 1~2개 능력의 공백부터 채운다.

## 12. 이번 패키지의 실제 코드 범위

### 구현·로컬 테스트

- v02의 공개 학습 후보 40개를 원본 변경 없이 import.
- 질문·근거·A/B·모델 실제 출력·기준 초안을 분리한 로컬 검토 UI.
- J7 캡처를 설명용으로 재구성한 2개 시연 사례.
- 원래 모델이 이유를 출력하지 않았을 때 ‘미출력’ 표시.
- 사례 해시, 중복 저장 방지, 검토자·이유·원문 확인·참고 초안 열람 기록.
- 모델 입력 export에서 기준 정답·해설·A/B 표시 제외.
- Crossref 검색 CLI: DOI 메타데이터 후보만 수집. 권리 승인·본문 취득은 하지 않음.

### 아직 구현하지 않은 연결

NASA collector, Docling parser, 교사 API 호출, 생성물 의미검증, PDF 원문 하이라이트, v08 실제 실행결과 import, LangGraph 전체 graph, 학습 자동예약·모델 승격은 위 설계에 따라 추가할 항목이다. 이번 UI에서 저장한 review JSONL을 기존 dcurr.review/prepare 계약에 연결하는 어댑터도 후속이다. CSV를 임의로 덮어쓰지 않는다.

이 패키지는 새 완성형 커리큘럼이 아니라 **기존 프로그램에 붙일 설계서+검토 중심 프로토타입**이다. 새 SFT 정답을 자동 승인하거나 기존 모델을 변경하지 않는다.

## 참고한 공식 자료

[R1] NASA STI, Harvesting Data from the NASA STI Repository. https://sti.nasa.gov/harvesting-data-from-ntrs/

[R2] Crossref, Accessing full texts / REST API. https://www.crossref.org/documentation/retrieve-metadata/text-and-data-mining/ ; https://api.crossref.org/

[R3] OpenAlex, API reference and filtering. https://help.openalex.org/api/ ; https://help.openalex.org/api/filtering/

[R4] Docling, DoclingDocument / ProvenanceItem. https://docling-project.github.io/docling/reference/docling_document/

[R5] OpenAI, Structured Outputs. https://developers.openai.com/api/docs/guides/structured-outputs

[R6] OpenAI, Batch API. https://developers.openai.com/api/docs/guides/batch

[R7] LangGraph, Persistence. https://docs.langchain.com/oss/python/langgraph/persistence

[R8] LangGraph, Interrupts. https://docs.langchain.com/oss/python/langgraph/interrupts

자료 확인일은 2026-09-20이다. API의 기능 확인과 사용자 환경에서의 실제 통합 실행 여부는 별도로 기록한다.
