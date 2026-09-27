# DoriLab Physics Seed32 v0.1

**작성일: 2026-09-13 · 문헌 기반 시험검토 SFT 후보 · 사람 검토 전**

우주 열진공·열평형과 힘 제한 랜덤진동 문헌의 원리를, 작은 언어모델이 수행할 **근거 검토 행동**으로 옮긴 첫 데이터 패키지다. 실제 계측 시계열이나 물리응답 대리모델의 학습 데이터가 아니다.

## 1. 이번에 완료한 범위

| 항목 | 결과 |
|---|---:|
| 서지·접근·이용조건 등록 | 기존 후보 12개 + 대체 논문 1개 = 13개 |
| 전문 PDF 텍스트 접근 확인 | 4개 |
| 실제 Seed 작성에 사용한 문헌 | TH-01 Apollo, VB-X1 Wijker 2015의 2개 |
| 페이지를 연결한 원문 기반 사실 | 16개 |
| 한 항목만 바꾼 대조쌍 | 16쌍 |
| SFT 후보 | 32개: 열 16 / 진동 16 |
| 정답 행동 분포 | NO_ACTION_REQUIRED 16 / CHALLENGE 10 / REQUEST_EVIDENCE 6 |
| 역할 | EVIDENCE 12 / CRITIC 20 |
| 사람 검토 완료 | 0개; review_decisions.csv에서 기록 |
| 이번 패키지의 독립 평가셋 | 없음 |
| 원문 바이너리 PDF/PPTX 포함 | 없음; 사용자 PC용 다운로드 도구 제공 |

모든 사례는 **SYNTHETIC_COUNTERFACTUAL**이다. 원문의 사실은 별도 `source_facts`에 요약하고, 사례의 가상 조건·제안·정답은 별도로 저장했다. 숫자가 등장하는 사례의 숫자도 가상값으로 표시했다.

기계적 구조 검사는 완료했지만, 실무자의 원문 대조와 정답 승인은 남아 있다. `32개 사례 = 32회 독립 시험`은 아니다. 2개 문헌의 16개 검토 주제를 2개씩 짝지은 개발용 Seed다.

## 2. 출처 확인에서 바뀐 부분

**Apollo:** NTRS 서지정보는 `1971-03-01`, PDF 표제지/보고서 페이지의 텍스트는 `March 1972`다. 문서번호 NASA-TN-D-6646과 NTRS ID 19720011230을 기준으로 식별하고 날짜를 둘 다 보존했다.

**Force Limited Vibration Testing Monograph:** NASA-RP-1403의 서지와 이용표시는 확인했지만 원문 PDF 요청이 403으로 차단됐다. 읽지 못한 모노그래프의 페이지를 근거로 사례를 작성하지 않았다. 이번 진동 16개는 전문과 CC BY 4.0을 확인한 Wijker·Ellenbroek·de Boer의 2015년 논문으로 대체했다. VB-01은 원래 후보로 유지하고 VB-X1을 별도 등록했다.

**Dynamic Finite Element Model Correlation:** 2022년 NASA 자료의 원본은 PPTX 발표자료다. 원문 유형과 파일명을 수정해 등록했다.

**접근 범위:** 이번 실행환경에서는 PDF 원문을 웹의 텍스트 추출 결과로 읽었으나, 바이너리 다운로드와 페이지 이미지 조회는 실패했다. 표·그림에서 수치를 추출하는 사례는 만들지 않았다. 원문 파일 SHA-256은 `null`이고, 실제 파일을 받은 뒤에만 취득 로그에 계산한다.

## 3. 파일 안내

| 경로 | 내용 |
|---|---|
| `docs/SOURCE_REGISTER.md` | 13개 출처의 제목·저자·문서번호·DOI·URL·이용표시·접근 상태 |
| `sources/source_manifest_v01.json` | 위 정보의 기계 판독형 등록부 |
| `data/source_facts_v01.jsonl` | 원문의 사실 16개, 영문·한글 요약, PDF/인쇄 페이지 |
| `data/physics_cases_seed32_v01.jsonl` | 32개 사례의 전체 주석: 가상 상태, 정답 후보, 한글 이유, 출처 |
| `data/physics_sft_seed32_candidate_v01.jsonl` | Hugging Face conversational messages 형식의 SFT 후보 |
| `data/pair_manifest_v01.json` | 각 대조쌍에서 바꾼 필드 위치 |
| `data/action_schema_v01.json` | 행동 출력의 JSON Schema |
| `runtime/physics_prompts_v01.py` | 학습·추론에서 공통으로 사용할 버전 고정 프롬프트 |
| `docs/CASE_REVIEW.html` | 브라우저에서 A/B를 나란히 읽는 검토 화면 |
| `docs/CASE_REVIEW.md` | 전체 사례의 편집·검토용 Markdown |
| `data/review_decisions.csv` | 사람 검토 기록. 최초 상태 전부 PENDING |
| `tools/validate_pack.py` | 해시·참조·페이지·대조쌍·프롬프트 검사 |
| `tools/fetch_sources.py` | 사용자 PC에서 원문 취득 및 실제 SHA-256 기록 |
| `tools/export_reviewed.py` | 승인한 대조쌍만 SFT로 내보내기 |
| `tools/run_seed_baseline.py` | 선택적 2B 개발용 추론 비교; GPU 실행은 제작 환경에서 미검증 |
| `reports/cpu_tests.txt` | 17개 CPU 단위시험 결과 |

## 4. Windows/WSL에서 시작하기

기존 `~/dorilab-ai/runtime`, `data/train150_v01.jsonl`, 모델 가중치와 프롬프트는 수정하지 않는다. 별도 하위 폴더에 압축을 푼다.

### 4.1 ZIP 옮기기

WSL에서 아래를 실행하면 현재 프로젝트 폴더가 Windows 탐색기로 열린다.

```bash
cd ~/dorilab-ai
source .venv/bin/activate
explorer.exe .
```

다운로드한 `DoriLab_PhysicsSeed32_v01.zip`을 열린 폴더에 복사한 뒤 WSL에서:

```bash
python -m zipfile -e DoriLab_PhysicsSeed32_v01.zip .
cd DoriLab_PhysicsSeed32_v01
python -m tools.validate_pack
python -m unittest discover -v
```

정상 결과는 `status: PASS`, `cases: 32`, `pairs: 16`, 그리고 `Ran 17 tests ... OK`다. 이 검사는 구조 검사이며 공학 정답의 독립 승인을 대신하지 않는다.

### 4.2 먼저 두 쌍 읽기

```bash
python -m tools.show_cases --pair TH01-P07
python -m tools.show_cases --pair VBX1-P03
explorer.exe docs
```

탐색기에서 `CASE_REVIEW.html`을 연다. 첫 쌍은 **히터 내부 센서와 평균 케이스 온도를 비교하는 문제**, 두 번째는 **힘 제한식에 사용할 모드의 선정 근거**다.

### 4.3 원문 취득

```bash
python -m tools.fetch_sources --ids TH-01 VB-X1
```

성공한 원문은 `sources/originals/`에 저장하고, 실제 파일 크기·해시·URL·상태는 `reports/source_acquisition_*.json`에 남긴다. HTML 차단 페이지를 PDF로 저장한 경우에는 검사를 통과하지 않는다.

403 등으로 실패하면 도구가 출력하는 공식 상세 페이지를 브라우저로 열어 받는다. 로컬 파일명은 `TH-01__19720011230.pdf`, `VB-X1__s12567-015-0086-0.pdf`다. 파일을 해당 이름으로 옮긴 뒤 도구를 다시 실행하면 형식과 해시를 기록한다. 서지와 일치하는 문서인지 표제지를 직접 대조한다.

전체 학습 후보 원문을 받으려면 `--all`을 사용할 수 있다. DEV/EVAL_RESERVED 자료는 기본적으로 건너뛴다. `--include-reserved`는 의도적으로 별도 원문 확인을 할 때만 선택한다. 다운로드 자체가 학습/RAG 등록을 수행하지는 않는다.

## 5. 검토 후 학습용 파일 내보내기

각 쌍을 읽고 `data/review_decisions.csv`를 편집한다.

- `decision`: PENDING / APPROVED / REVISE / REJECTED
- `reviewer`: 실제 검토자 식별
- `reviewed_at`: 실제 검토일, 예: `2026-09-13`
- `notes`: 출처 대조, 정답 수정 요청, 적용 범위에 대한 의견

A/B 모두 적절한 쌍을 승인한 뒤:

```bash
python -m tools.export_reviewed
```

`data/physics_sft_reviewed_v01.jsonl`과 대응 manifest가 만들어진다. 승인된 쌍이 없으면 파일을 만들지 않고 알려준다. 정답을 바꿔야 하는 사례는 REVISE로 기록하고 새 버전에서 정정한다. 원본 후보와 해시를 보존해 어떤 판단이 바뀌었는지 남긴다.

## 6. 기존 2B를 먼저 비교할 때

아래는 선택적 개발 검사다. 새 모델을 학습하지 않으며 현재 32개 후보를 읽어 JSON·행동·근거 참조를 확인한다. 명령은 **이 패키지 폴더 안에서** 실행한다.

```bash
python -m tools.run_seed_baseline --label seed32_base --limit 4

python -m tools.run_seed_baseline \
  --adapter ../adapters/dorilab-qwen35-2b-v01 \
  --label seed32_contract_lora --limit 4
```

전체 32개를 볼 때는 `--limit 32`와 새로운 `--label`을 사용한다. 출력은 `reports/`에 저장한다. 모델 준비·추론 코드의 문법 검사는 수행했지만, 이 제작 환경에서는 GPU나 Hugging Face 모델을 실행하지 않았다. 사용자 PC에서 확인된 멀티모달 auto-loader 경로를 우선 사용한다.

이번 프롬프트는 `physics-review-v0.1`이다. 기존 Contract150 프롬프트와 다른 업무·출력 계약이므로 기존 20/20 수치와 단순 비교하지 않는다. 기본 2B와 기존 LoRA를 **동일한 새 프롬프트**로 비교하는 자료다.

## 7. 이어서 학습할 때의 기준

사람이 검토한 Physics 사례부터 v0.2 학습에 사용한다. 기존 Contract150은 회귀용으로 보존한다. 두 종류를 혼합할 경우 각 예제의 system prompt와 schema version을 그대로 유지하고, 입력 역할에 맞는 공통 프롬프트로 추론한다. 기존 LoRA를 덮어쓰지 않고 clean base + 새 adapter로 실험한다.

새 프롬프트와 참조 문맥이 더 길어졌으므로 **token 길이를 먼저 재고**, 정답 completion이 잘리지 않도록 학습 길이를 정한다. 기존 `max_length=1024`를 그대로 적용하면 원문 맥락이나 정답이 잘릴 수 있다. 이 패키지의 baseline runner는 긴 입력을 조용히 자르지 않고 중단한다.

32개는 한 번 학습을 실행하는 Seed 규모다. 모델이 근거가 바뀔 때 판단을 바꾸는지, 참조를 정확히 붙이는지, 적절한 제안도 수용하는지 확인한 뒤 문헌·프로그램을 늘린다.

## 8. 평가 분리

같은 원문·시험 프로그램·대조쌍에서 파생한 사례는 같은 분할에 둔다. 문서 제목만 달라도 동일 시험을 재분석한 문헌은 관련될 수 있다. 등록부의 프로그램 그룹은 그 검토를 돕는 초기 태그이며, 전체 독립성이 확인된 것은 아니다.

평가에서 처음 보는 논문의 원문 일부를 입력 또는 허용된 검색 결과로 주는 것은 **근거를 읽는 업무 자체**다. 원문 접근과 정답 라벨 노출을 구분한다. 평가 정답·해설·미래 결과를 모델 입력이나 학습으로 넘기는 경로는 따로 차단한다. 이번 패키지에는 실제 sealed 문항을 만들지 않았다.
