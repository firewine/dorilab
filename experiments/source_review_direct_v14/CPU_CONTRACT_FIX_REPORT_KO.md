CPU 작업을 완료했다. 별도 `experiments/source_review_direct_v14`에 출력 안내만 수정한 프롬프트, DEV8 입력, CPU 검사, 다음 GPU 배치 runner와 비교 도구를 준비했다. RunPod를 켜지 않았고 모델 로드·추론·LoRA 학습을 실행하지 않았다. 새 모델 출력이나 개선 점수는 없다.

실제 과거 입력 확인

`FINAL_REPORT_KO.md`, 상위·baseline `RUN_MANIFEST.json`, `SUMMARY.json`, `CASE_RESULTS.jsonl`, `RAW_OFFICIAL_CASE_RESULTS.jsonl`, 저장 DEV8 입력, `packtool.py` render 경로와 `scripts/run_baseline.py`를 읽었다. 기존 보고서만으로 입력을 추정하지 않고 저장 파일 bytes와 과거 manifest를 대조했다.

- 저장 파일: `results/source_review_v13_qwen27/inputs/dev8_hypso_public_v13_source_available_v1.jsonl`.
- SHA256 `d050c092f2b0857569d8975a944cc759daed2df69f61ee395009372802e7ba41`가 상위 및 baseline manifest의 input hash와 일치한다.
- 저장 메시지 8건의 system 내용이 원본 `prompts/direct_v13.txt`와 모두 동일하다. 각 messages hash도 보존된 predictions의 같은 case hash와 일치한다.
- 당시 runner SHA256 `313b9ca0660c45f7fff8a6e499b5c8105f661f1714dc7d7c427f11d66ac5d07c`가 baseline manifest의 runner hash와 일치한다.
- 이 실제 입력은 적용 가능한 reason code를 포함하라고 설명하지만 JSON key를 `"reason"`으로 명시하지 않는다. action JSON Schema도 메시지에 없다. 원본 render는 공개 입력·facts·prompt만 읽으며 action schema를 삽입하지 않는다. 저장 runner도 입력 메시지에 native chat template를 적용할 뿐 schema를 추가하지 않는다.
- 따라서 사용자가 지적한 출력 안내의 불명확성이 **실제 DEV8 저장 메시지에도 해당함을 확인했다**. 다만 이 사실만으로 출력 실패의 인과나 수정 효과가 입증되는 것은 아니다.
- 당시 최종 chat-template 렌더링 텍스트와 입력 token ID 전체는 확인한 baseline 산출물에 저장되어 있지 않다. predictions에는 rendered prompt hash와 token 수가 있다. 이번에 당시 최종 token stream을 복원·확인했다고 주장하지 않는다. 현재 코드로 재구성한 입력을 과거 원본으로 표시하지 않았다.
- baseline manifest의 `status=STARTED`는 그대로 두었다. 완료 여부에 관한 OUTPUT_SEAL과 후속 보고서가 별도로 존재한다. 누락된 과거 정보를 채우거나 status를 고치지 않았다.

상세 근거는 [HISTORICAL_INPUT_AUDIT.json](audit/HISTORICAL_INPUT_AUDIT.json)에 있다.

변경한 출력 안내

[direct_v14.txt](prompts/direct_v14.txt)는 기존 prompt의 출력 필드 안내 부분만 대체했다. Action 의미를 설명하는 앞부분과 도구 실행 비인가·Human Review 안내를 포함한 뒷부분, reason 정의 전체는 원문 그대로다. 새 system 메시지 외에는 DEV8의 순서·case_id·user 메시지 문자열이 모두 같다. 사례 본문, facts, 후보 gold, reason 분류 정의, JSON Schema와 scorer 파일을 변경하지 않았다. review ledger, constrained decoding, product adapter, 출력 재시도·교정도 도입하지 않았다.

공통 필수 필드는 `action`, `claim_id`, `evidence_refs`이다. 아래 각 Action에서 명시된 필드 이외에는 모두 생략하도록 안내했다.

| Action | 공통 필드 외 필수 | 이번 계약에서 생략 |
|---|---|---|
| NO_ACTION_REQUIRED | 없음 | reason, requested_evidence, tool, arguments, finding_type |
| CHALLENGE | reason | requested_evidence, tool, arguments, finding_type |
| REQUEST_EVIDENCE | reason, 비어 있지 않은 requested_evidence | tool, arguments, finding_type |
| CALL_TOOL | 문자열 tool, 객체 arguments | reason, requested_evidence, finding_type |
| PROPOSE_FINDING | 문자열 finding_type | reason, requested_evidence, tool, arguments |

`reason_code`를 사용하지 않고 정확히 `reason`을 사용한다. claim_id는 제공값 그대로, evidence_refs는 판단을 뒷받침하는 제공된 source/observation ID만 중복 없이 선택한다. 모든 ID 일괄 인용, 누락 근거 추정, 관련 없는 필드와 관성적인 빈 배열 추가를 금지했다. 요청은 제공된 request_catalog ID만 사용한다. 필수 evidence_refs 자체는 생략하지 않으며 뒷받침할 제공 ID가 전혀 없는 경우의 빈 배열은 기존 스키마가 허용하는 범위임을 구분했다. 출력은 Markdown 없는 JSON 객체 하나다.

프롬프트의 예시는 `CLM-FORMAT-DEMO` / `OBS-FORMAT-DEMO`라는 새 가상 ID로 작성한 문법 예시이다. 평가 사례의 정답을 복사하지 않았다. 예시에는 의미 판단 사례나 정답 reference 집합을 넣지 않았다. 추가 검사의 다섯 Action fixture도 수작업 문법 검사 자료이며 모델 입력에 추가하지 않는다. 실제 DEV8은 기존 세 Action 범위이며 CALL_TOOL/PROPOSE_FINDING 검사 통과를 도구 통합이나 의미 판단 검증으로 해석하지 않는다.

CPU 검사와 확인한 경계

| 검사 | 결과 | 기록 |
|---|---:|---|
| 기존 단위검사 | 34/34 PASS | audit/original_34_tests.log |
| 추가 단위검사 | 31/31 PASS | audit/new_tests.log |
| 원본 packtool validate | PASS | audit/original_validate.log |
| 새 Python 코드 구문 검사 | PASS | AST parse; 모델 import/실행 없음 |
| 원본 보존 | 197개 파일 bytes 동일, 원본 경로 신규 파일 0 | audit/PRESERVATION_AFTER.json |
| 새 실제 token 길이 | 미측정 | audit/TOKEN_PREFLIGHT_STATUS.json |

기존 34개 검사는 수정하지 않았다. 추가 31개는 별도 tests 폴더에 있다. Action별 필드 목록과 기존 JSON Schema의 조건부 required 집합, 프롬프트 예시의 schema/scorer 통과, reason_code, reason 누락, 빈 요청, 불필요 필드, 미제공 reference·request, claim 불일치, 중복 reference, 모든 ref 무조건 인용, Markdown/복수 JSON, 입력 누수와 필드·Action 집계 구분, 예산 초과 중단을 검사한다.

입력 생성기 전체를 파일 읽기 허용목록 아래 실행해 gold·rationale·정답 reference 집합 파일을 읽지 않음을 검사했다. 중첩된 정답 관련 key 주입도 거부하며 원래 공개 user 메시지를 byte 수준 문자열 비교로 보존한다. 원본 render와 달리 새 입력 생성은 현재 facts에서 과거 메시지를 재조립하지 않고, hash가 일치하는 저장 DEV8에서 system 메시지만 교체한다.

기존 스키마와 scorer는 동일한 제약 집합이 아니다. 이를 숨기거나 이번 실험에서 수정하지 않았다.

- 알려진 선택 필드라도 해당 Action에 불필요하면 JSON Schema/check_answer는 일부 허용할 수 있지만, 기존 strict는 후보의 정확한 key 집합과 다르면 실패한다. 새 prompt는 Action별 최소 필드 집합을 안내한다. 별도 `contract.violations`는 진단 메타데이터이며 공식 scorer를 대체하지 않는다.
- CHALLENGE의 `requested_evidence: []`는 JSON Schema의 minItems 위반이다. 기존 check_answer는 REQUEST_EVIDENCE에서만 비어 있지 않은 요청을 요구하므로 CHALLENGE에서는 schema 단계 통과가 가능하지만 strict는 실패한다. 이 차이를 별도 회귀 검사로 남겼다. 새 prompt는 CHALLENGE에서 해당 필드를 생략한다.
- 미제공 reference와 claim_id 불일치는 정적 JSON Schema만으로 검사할 수 없으며 packet에 의존하는 기존 scorer가 거부한다.
- 이번 비교의 `schema_valid`는 기존 공식 scorer의 check_answer 결과이다. 문서 JSON Schema와의 일치 검사는 별도 CPU 검사이며 기존 공식 지표 정의를 바꾸지 않는다.

추가 검사 첫 실행에서 허용목록이 생성 직후 입력 파일의 자체 hash 읽기를 누락하여 1건 실패했다. 허용목록에 그 파일을 추가한 후 31개 모두 통과했다. 초기 실패 로그는 `audit/new_tests_initial_failure.log`에 보존했다. 이는 검사 코드의 누락이었으며 gold 읽기를 허용하도록 변경한 것이 아니다.

이 결과는 구조·출력 계약·누수 방지·준비 코드의 CPU 검사이다. 모델이 새 안내를 따를지, Action/reason/reference/strict가 개선될지는 **미검증**이다. GPU runner의 실제 runtime 실행도 미검증이다.

다음 GPU 배치 계획

실행 명령은 [GPU_BATCH_COMMANDS.md](GPU_BATCH_COMMANDS.md)에 있다. 이번에는 실행하지 않았다. 새 runner는 과거 runner의 생성 경로를 유지하면서 입력과 출력 버전을 direct_v14로 분리하고, 모델 로드 전 실제 token 검사와 새 실행의 렌더링 입력 저장을 추가했다.

고정 model revision은 `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Transformers commit은 `002e1edf5b5198488297f401dd853056b6521d02`이다. BF16, SDPA, greedy, seed42, native template, enable_thinking=false, 응답384/총2048 token을 유지한다. 기존 generation_config와 종료 token 처리도 동일 경로를 사용한다.

현재 환경에는 과거 기록의 snapshot 디렉터리가 없다. 새 prompt의 실제 token 길이를 추정값으로 채우지 않았다. 후속 환경에서 동일 tokenizer/template/commit으로 측정하며, 입력+384가 2048을 넘는 사례가 있으면 실제 길이를 기록한 뒤 **모델 로드 전에 중단**한다. 몰래 자르거나 응답 예산·문맥 한도를 바꾸지 않는다. 한도 초과 시 새 명시적 수정본 준비가 필요하다. token 측정 통과 전에는 GPU 실행 준비 조건이 모두 충족됐다고 볼 수 없다.

새 실행은 `runs/direct_v14`에 저장하며 기존 direct 결과를 재실행하거나 덮어쓰지 않는다. 새 predictions의 hash를 먼저 봉인한 뒤 별도 CPU 비교 프로세스가 미승인 후보 gold를 읽는다. 기존 기준은 저장된 RAW_OFFICIAL_CASE_RESULTS를 읽으며 재채점하지 않는다.

| 비교 지표 | 기준 DEV8 | 새 direct_v14 |
|---|---:|---|
| JSON 유효 | 8/8 | 실행 후 집계 |
| 기존 scorer schema 유효 | 4/8 | 실행 후 집계 |
| reason_code 사용 | 4/8 | 다른 필드 위반과 함께 별도 집계 |
| 파싱된 Action 일치 | 8/8 | schema 실패 포함, 별도 표시 |
| schema 통과 후 Action 일치 | 4/8 | 별도 집계 |
| reference exact | true 3 / false 1 / 미평가 4 | 세 상태 구분 |
| strict | 3/8 | 실행 후 집계 |
| 생성 시간 | 총 38.68443450704217초 | 총합·사례별 시간·token 수 |

사례별 JSON/schema/Action/reference/strict 변화를 기록하고 개선과 회귀를 모두 표시한다. reference 미평가에서 평가 가능으로 바뀐 경우도 별도로 표시한다. 생성 시간 비교에는 실제 GPU/runtime과 길이 차이를 함께 남긴다. CPU 통과 수를 이 표의 새 모델 성능으로 옮기지 않는다.

DEV8은 **한 출처·두 관련 family의 이미 관측한 진단 집합**이다. 정답 상태는 계속 SOURCE_GROUNDED_AI_CANDIDATE, human_review_performed=false, training_eligible=false이다. 독립 일반화 평가나 학습 데이터로 사용하지 않는다. 독립 사람 검토·label release가 완료되었다고 표현하지 않는다.

산출물과 보존

- [프롬프트 변경 diff](PROMPT.diff), [코드·검사 변경 diff](CHANGES.diff).
- [새 DEV8 입력](inputs/dev8_direct_v14.jsonl), [실험 조건](EXPERIMENT_LOCK.json).
- [추가 계약 검사](tests/test_contract_v14.py), [배치 조건 검사](tests/test_batch_guard.py), [비교 집계 검사](tests/test_comparison.py).
- [CPU 검사 결과](audit/CPU_TEST_RESULTS.json), [입력·코드 hash](INPUT_CODE_HASHES.json), 전체 산출물 `SHA256SUMS.txt`.
- [다음 GPU 명령](GPU_BATCH_COMMANDS.md), [미래 runner](scripts/run_direct_v14.py), [사후 비교 도구](scripts/compare_results.py).

새 입력 SHA256: `7b50842f8abed5e621c69b4c03a924d8a6228c6f624200d2420b8cc9c8304232`.
새 prompt SHA256: `c2f9b03b6990eb6ea7c6403a11e7899ba251e95f4d57907384685f94e2b16dae`.
원본 scorer SHA256: `e1a81cb761ebbecae51e026b4f99122a0cac748aa548ca113ee6e318b6445fca`.
기존 raw 출력 SHA256: `c0be480c5b772ba3df09ceb9ead8b9e5f9023591d29aea2d2c9c14700c56585c`.

원본 패키지·기존 결과 총197개 파일에 대해 시작/종료 hash가 같다. 기존 raw output의 reason_code를 reason으로 바꾸지 않았고 공식 점수도 덮어쓰지 않았다. 기존 모델 출력과 gold를 새 프롬프트의 예시로 복사하지 않았다. CPU 작업 산출물을 보고한 뒤 대기한다.
