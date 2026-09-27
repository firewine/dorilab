# DoriLab 입출력 명세서

문서 ID: `DORI-IO-001` | 버전1.0 | 2026-09-27 UTC.

기준: [소스 hash](SOURCE_BASELINE.json). 본 문서는 **현재 실행 형식**을 기술한다. 모델 출력의 구조와 업무 판단은 HTTP 완료 후 별도 검증한다.

## 1. 인터페이스 목록

| 경계 | 입력 | 출력 | 전송/호출 |
|---|---|---|---|
| 기억 저장 | project, trajectory, 선택적 expected_version | version, duplicate, source_hash | Python/CLI |
| 기억 조회 | project, question, scope, pool 질의, 예산 | evidence bundle | Python/CLI |
| 원문 조회 | project, trajectory_id, start/stop | step span | Python/CLI |
| 검색 제어 | 질문, 후보, 원문, 한도 | search/inspect/finish JSON | Qwen 계약을 사용하는 기존 HTTP |
| 검토 준비 | SourceReview packet, 근거 묶음 | request + memory + receipt | Python/CLI |
| 생성 제출 | request_id, contract_id, user 문자열, 응답 예약 | 202 job ID | POST /v1/generations |
| 생성 조회 | job ID + Bearer token | running/completed/failed | GET /v1/generations/{id} |

기억 저장과 검색은 Python/CLI로 호출한다. planner와 RC3 검토의 HTTP 경로는 같은 generation API다.

## 2. 공통 표현과 검증

JSON은 UTF-8로 취급한다. 표의 문자열 길이는 Python 문자 수이며, byte로 표시한 제한은 UTF-8 인코딩 길이다. 시각은 timezone을 가진 ISO-8601 문자열을 입력하고 비교 시 UTC로 변환하되 원래 문자열은 보존한다. API job created_at은 Unix epoch 초 실수다.

project_id와 trajectory_id는 `^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$`를 따르며 `..` 검출 시 검증 오류로 처리한다. HTTP request_id의 규칙은 §8을 따른다.

기억 CLI의 strict_loads와 기억 입력 검증은 중복 JSON key, 비유한 수, 다음 예약 chat delimiter를 거부한다: `<|im_start|>`, `<|im_end|>`, `<|endoftext|>`.

다음 key는 중첩 object에서도 입력 메타데이터로 거부한다.

```text
gold, expected, rationale, rationale_ko, reference_answer,
sufficient_sets, acceptable_reason_codes, reference_requirement,
training_eligible, supporting_fact_ids, supporting_observation_ids
```

이 검사는 입력 key를 기준으로 수행한다. 자연어 의미 분류는 별도 검증 대상이다. 모델 출력과 receipt 파일은 원문 보존용 데이터로 읽는다. raw_text에는 정상 종료 토큰이 포함될 수 있다.

## 3. 기억 입력: Trajectory

root에는 아래 다섯 필드가 모두 필요하며 추가 필드는 거부한다.

| 필드 | 형식/필수 | 코드 제한 |
|---|---|---|
| trajectory_id | string, 필수 | 공통 identifier 규칙 |
| source | object, 필수 | 정확히 uri/revision 두 필드 |
| source.uri | string, 필수 | 비공백, 최대1024자; 위치 설명용 metadata |
| source.revision | string, 필수 | 비공백, 최대128자; 문자열 일치로 비교 |
| scope | object, 필수 | 정확히 unit_id/configuration_id/run_id |
| scope의 각 값 | string, 필수 | 비공백, 최대128자 |
| steps | array, 필수 | 1..100개 |
| notes | array, 필수 | 0..30개 |

trajectory 전체 canonical JSON은512KiB 이하여야 한다. source_hash의 계산 대상은 trajectory JSON 전체다. 외부 URI 파일의 무결성은 별도 검증 대상이다.

각 step은 다음 세 필드만 허용한다.

| 필드 | 형식 | 제한 |
|---|---|---|
| observed_at | string | timezone 포함 ISO-8601; steps 배열에서 비감소 순서 |
| observation | string | 비공백, 최대12,000자 |
| action | string | 최대2,000자; action 기록 생략 시 빈 문자열 |

각 note는 다음 네 필드만 허용한다.

| 필드 | 형식 | 제한 |
|---|---|---|
| kind | enum | workflow / gotcha / premise |
| text | string | 비공백, 최대4,000자 |
| status | enum | candidate / confirmed |
| step_indices | integer array | 한 개 이상의 고유 정수(type=int), 0≤index<len(steps) |

confirmed는 신뢰된 입력 작성자의 검토 표시이며 사실성 판단은 작성자의 책임이다. candidate와 confirmed 모두 원본에 보존하며 검색 pool에는 confirmed를 사용한다.

유효한 합성 입력 예:

```json
{
  "trajectory_id": "sensor-input",
  "source": {"uri": "synthetic://project/input", "revision": "1"},
  "scope": {"unit_id": "SYN-UNIT", "configuration_id": "SYN-CONFIG", "run_id": "SYN-RUN"},
  "steps": [
    {"observed_at": "2026-09-27T00:00:00Z", "observation": "Synthetic input record is missing.", "action": "Attach the synthetic record."},
    {"observed_at": "2026-09-27T00:01:00Z", "observation": "Synthetic input record is present.", "action": ""}
  ],
  "notes": [
    {"kind": "workflow", "text": "Attach the record before checking its presence.", "status": "confirmed", "step_indices": [0, 1]}
  ]
}
```

프로젝트 ID는 호출 인자로 전달한다. 같은 trajectory를 다른 프로젝트에 넣으면 source_hash가 같을 수 있지만 evidence_id는 프로젝트를 반영하여 계산한다.

### 3.1 삽입, 개정, 철회 결과

`insert` 반환 필드는 version(string SHA256), duplicate(bool), source_hash(string SHA256)다. 동일 활성 내용의 재입력은 duplicate=true이며 기존 version을 유지한다. expected_version을 전달했다면 중복 판단 전에 현재 version과 비교한다.

기존 활성 trajectory 교체에는 새 source.revision과 expected_version이 필요하다. source.revision 문자열은 해당 trajectory의 전체 이력에서 고유해야 한다. 철회 후 재삽입에도 변경된 새 revision이 필요하다.

`withdraw`의 Python 반환은 새 version 문자열, CLI 반환은 `{"version": "..."}` 객체다. 철회 시 이전 원문/revision은 이력에 보존한다.

### 3.2 영구 snapshot과 manifest

| state.json 필드 | 형식/의미 |
|---|---|
| schema | `dorilab.project-memory.v1` |
| project_id | 프로젝트 identifier |
| sequence | 최초 빈 상태0, 성공한 commit마다1 증가 |
| revisions | `{source_hash, trajectory}`의 배열; 철회, 대체된 원문도 포함 |
| active | trajectory_id → 활성 source_hash mapping |
| version | version key 제거 후 snapshot 전체의 canonical hash |

프로젝트 한도는 snapshot32MiB, 누적 revision1000개다. 초기 프로젝트의 manifest는 가상 빈 상태를 반환할 수 있다. state.json 생성은 삽입 시 수행한다.

manifest 반환은 schema/project_id/version/sequence/active_trajectories/retained_revisions다. active_trajectories 각 항목에는 trajectory_id, source, scope, source_hash, steps(개수), pools(생성된 pool별 개수)가 있다. pools mapping에는 실제 생성된 pool의 개수를 기록한다.

### 3.3 원문 구간

`inspect(project, trajectory_id, start=0, stop=None)`은 활성 trajectory만 조회한다. 범위는 `[start, stop)`이며 stop=None은 마지막 step까지다. `0≤start<stop≤len(steps)`를 만족해야 한다.

반환 필드: project_id, version, source_hash, source, scope, trajectory_id, start, stop, steps. note가 여러 step을 참조하면 제어기는 최소 index부터 최대 index+1까지의 연속 구간을 조회한다. 두 index 사이의 step도 포함된다.

## 4. 검색 입력과 Evidence Bundle

| 인자 | 기본값 | 제한/의미 |
|---|---|---|
| project | 필수 | AccessScope 권한 확인 |
| question | 필수 | 비공백 string, 최대4,000자 |
| scope | 필수 | 세 scope 값 정확히 일치 |
| queries | null | null이면 raw/events/notes 모두에 question 사용 |
| queries 각 값 | — | 직접 검색은 비공백 string 최대4,000자 |
| top_k | 6 | 직접 검색1..30, 제어기 사용 시1..6 |
| max_bytes | 12000 | 정수256..50000; evidence 배열 선택 예산 |

queries에는 raw/events/notes 중 하나 이상을 지정하며 검색 대상은 지정한 pool이다. `max_bytes`는 선택된 evidence 배열의 canonical UTF-8 byte 예산이다.

### 4.1 Evidence 항목

| 필드 | 형식/의미 |
|---|---|
| evidence_id | `MEM-` + 프로젝트/source_hash/pool/index hash 앞32자리 |
| project_id / trajectory_id | 출처 식별자 |
| pool | raw / events / notes |
| scope / source / source_hash | 원본 범위, 개정, 내용 식별 |
| text | 원문 또는 기록된 변화의 렌더링, 확인된 note |
| step_indices | 근거 step 번호 배열 |
| observed_at | raw는 해당 step, events는 후속 step 시각; raw/events 전용 필드 |
| kind / status | notes에만 추가; status는 confirmed |
| score | 해당 pool 검색의 BM25 점수, 소수점6자리 반올림 |

score는 각 pool의 BM25 검색 순위 계산에 사용한다. pool별 순위를 유지하며 raw/events/notes 순서로 병합한다. 신뢰도, 확률, 근거 충분성은 별도 판단 대상이다.

### 4.2 Bundle 반환

| 필드 | 형식/의미 |
|---|---|
| schema | `dorilab.project-memory.v1` |
| project_id / version / question / scope | 질의와 기준 snapshot |
| evidence | 선택된 Evidence 배열 |
| excluded | `{evidence_id, reason}` 배열; reason은 top_k 또는 byte_budget |
| evidence_bytes | 선택된 evidence 배열의 canonical UTF-8 byte 수 |
| status | evidence_found / no_evidence |
| cache_hit | 직접 검색의 LRU 적중 여부; controller 최종 bundle은 false |
| retriever | `bm25-korean-bigrams-v1` |
| streams | 직접 검색에 사용된 pool 이름; controller 결과에서는 baseline의 값 |
| selection_policy | 선택 방식 설명 문자열 |
| bundle_hash | cache_hit과 bundle_hash key 제거 후 bundle의 canonical hash |
| controller | 제어기 사용 시에만 추가되는 §5.3 객체 |

제어기 결과의 excluded는 최종 선택 ID 중 예산 초과로 보류한 항목 목록이다. 중간 질의는 controller.trace의 search 계획과 planner request 증적으로 확인한다. 후보와 원문은 항목 전체 단위로 선택한다.

## 5. Qwen 검색 제어 입출력

### 5.1 Qwen에 전달하는 context

JSON context가 generation API의 `user` 문자열 안에 직렬화된다.

| 필드 | 형식/의미 |
|---|---|
| question | 원래 질문 |
| scope | 코드가 고정한 scope |
| candidates | 이번 계획 호출에 제시한 Evidence 배열 |
| inspected | evidence_id → inspect 원문 구간 mapping |
| searches | 수행한 pool별 query mapping의 이력; baseline 포함 |
| remaining_searches | 남은 추가 검색 횟수 |
| remaining_steps | 현재 호출을 포함한 남은 제어 단계 |
| omitted_candidates | context byte 예산 때문에 이번 호출에서 제외한 ID |

기본 context 예산은10,500byte, 라이브러리 허용 범위2,000..14,000byte다. 후보와 원문 span은 각각 context 예산의 적용을 받는다. inspected mapping에는 이번 context에 들어간 원문 ID를 기록하며 이 mapping으로 원문 열람 여부를 판단한다. ID 검증은 이번 호출에서 보인 candidates를 기준으로 한다.

### 5.2 Planner 응답 계약

각 action의 필드는 정확히 아래 형식이어야 한다. Markdown, 추가 필드, 중복 key, 미등록 후보 ID는 검증 오류로 처리하며 응답 원문을 보존한다. 응답 텍스트 자체의 parser 한도는12,000byte다.

```json
{"action":"search","queries":{"raw":"sensor record presence","events":"record attached transition","notes":"input readiness procedure"}}
```

search는 pool1..3개, 질의별 비공백 최대600자다. 허용 root 필드는 action과 queries이며 project_id, scope, system, 경로, 명령 등의 추가 필드는 검증 오류로 처리한다.

```json
{"action":"inspect","evidence_ids":["MEM-77a2687584ce0260542f7b0a806abcf7"]}
```

inspect는 현재 후보의 고유 ID1..3개다. 제시된 ID 모두가 이미 조회된 상태면 repeated_inspection으로 종료한다. 일부만 새 ID인 경우 전체 요청을 실행할 수 있다.

```json
{"action":"finish","evidence_ids":["MEM-77a2687584ce0260542f7b0a806abcf7"],"assessment":"sufficient","missing":[]}
```

finish는 고유 ID0..6개다. assessment는 sufficient/insufficient/conflict, missing은 비공백 최대300자 문자열0..3개다. sufficient에는 최소1개 ID와 빈 missing이 필요하다. 예제의 MEM ID는 실제 합성 검증에서 사용한 값이다. 각 ID는 현재 프로젝트의 제시된 후보 집합에 속해야 한다.

코드가 finish 결과를 만들 때 모든 선택 근거의 원문 출처를 확인한다. sufficient 판정에는 이번 Qwen context에서 선택 원문을 열람한 기록이 필요하다. 열람 조건 또는 최종 선택 예산을 위반하면 controller.assessment를 insufficient로 낮춘다. 모델 원문과 trace.plan은 그대로 보존한다.

### 5.3 Controller 반환 부가 필드

| 필드 | 값/의미 |
|---|---|
| schema | `dorilab.search-controller.v1` |
| planner | qwen-base-v1 / rules-v1; 사용자 정의 planner는 자체 name |
| stop_reason | finished / deadline / context_budget / planner_error / repeated_inspection / repeated_query / search_limit / step_limit |
| fallback | baseline 복귀 여부 |
| assessment | sufficient / insufficient / conflict; 항상 참고 판단 |
| assessment_is_advisory | true |
| missing | 최종 제어 상태의 부족 정보 |
| searches | baseline을 포함한 검색 횟수 |
| steps | trace 항목 수; schema 실패 시 error 항목도 포함 |
| trace | `{step, plan, plan_sha256}` 또는 `{step, error_type}` |
| inspected | ID → source_hash/span_sha256/start/stop; 원문 본문은 planner trace나 inspect에서 조회 |
| elapsed_seconds | 근거 수집 단계의 관측 시간 |

메모리 version 변경은 ConflictError로 중단한다. token 파일 누락이나 trace 디렉터리 충돌 같은 QwenPlanner 생성 전의 설정 오류도 직접 중단 처리한다. baseline 복귀는 생성 완료된 제어기의 실행 단계에 적용한다.

## 6. SourceReview packet 입력

bridge.prepare의 root 필드는 아래8개로 고정한다. 이는 HTTP 외피와 구별되는 native 입력 객체다.

| 필드 | 모델 계약상 의미 | 현재 bridge 코드 검증 |
|---|---|---|
| claim_id | 검토 항목 string ID | root 필드 존재; 세부 타입 강제는 제한적 |
| review_question | 검토 질문 string | 검색 시 비공백/최대4,000자 |
| review_target | kind/text 등 검토 대상 object | 코드 검증: root 존재; 내부 schema는 모델 계약 |
| scope | 대상 범위 object | 정확한3개 key, 각 비공백 문자열≤128자 |
| source_refs | source reference 배열 | list, 각 reference_id는 문자열이며 전체 근거 ID에서 고유 |
| observations | 관찰 배열 | list, 각 evidence_id는 문자열이며 전체 근거 ID에서 고유 |
| request_catalog | 요청 가능한 자료 목록 | 코드 검증: list 타입; 내부 schema는 모델 계약 |
| scope_of_result | 결과 적용 범위 설명 | 코드 검증: root 존재 |

권장 입력의 완전한 예는 [합성 packet](../../project_memory/examples/packet.json)을 따른다. root 추가 필드, 제한 key/예약 delimiter, 근거 ID 충돌은 거부한다. 코드 검증 범위는 위 표를 따르며 모델 계약의 의미와 내부 field는 별도 검증 대상이다.

bridge가 추가하는 observations 항목은 다음 형태다.

```json
{
  "evidence_id": "MEM-77a2687584ce0260542f7b0a806abcf7",
  "display_id": "MEM-77a2687584ce0260542f7b0a806abcf7",
  "scope": {"unit_id":"SYN-UNIT","configuration_id":"SYN-CONFIG","run_id":"SYN-RUN"},
  "text": "Memory provenance: {출처 metadata의 canonical JSON}\n관찰 원문",
  "origin": "PROJECT_MEMORY_RAW"
}
```

위 text는 렌더링 형식을 설명하는 예다. 실제 metadata는 pool/source/source_hash/trajectory_id/step_indices, 있을 때 observed_at을 포함한다. origin은 PROJECT_MEMORY_RAW / PROJECT_MEMORY_EVENTS / PROJECT_MEMORY_NOTES다. 기존 source_refs나 observations는 복사하여 보존한다.

## 7. 검토 준비 결과와 최종 모델 출력

prepare 반환 root는 request/memory/receipt다. API에 보내는 것은 request만이다.

| receipt 필드 | 의미 |
|---|---|
| schema | `dorilab.memory-preparation.v1` |
| project_id / memory_version | 조회 프로젝트와 snapshot |
| bundle_hash / evidence_ids | 선택 근거 묶음과 ID |
| user_sha256 | 실제 native user 문자열의 UTF-8 SHA256 |
| native_input_tokens | 로컬 native 검사 사용 시 정수, 검사 생략 시 null |
| token_budget_validation | local-native / server-before-202 |
| original_packet_sha256 | 근거 추가 전 packet canonical hash |
| output_used_as_memory | false |

검토 완료 receipt는 위 필드에 boot_id/model_receipt_id/job_id/output_sha256/purpose를 추가한다. 현재 purpose는 코드에 고정된 integration smoke 설명 문자열이다. 업무 유형 분류에는 별도 metadata가 필요하다.

기본 SourceReview 모델 출력 계약:

| action | 정확히 요구하는 key |
|---|---|
| NO_ACTION_REQUIRED | action, claim_id, evidence_refs |
| CHALLENGE | 위3개 + reason |
| REQUEST_EVIDENCE | 위3개 + reason + requested_evidence |

evidence_refs는 제공한 source reference_id 또는 observation evidence_id로 구성된 고유 ID 배열이다. 제공 근거0개이면 빈 배열을 사용한다. requested_evidence는 제공한 request_catalog에서 선택한 고유 ID1개 이상의 배열이다. 허용 reason 목록은 [서비스 계약](../../inference/contracts/service_contracts.json)의 정의를 따른다.

이 형식은 **모델 출력 계약**이다. 일반 bridge.generate와 HTTP 서비스는 모델 원문을 제공한다. 출력 JSON의 업무 schema와 판단 유효성은 status=completed 후에도 호출자가 별도 검증해야 한다. 합성 검증의 파싱/근거 ID 검사도 별도 검증 작업으로 수행했다.

## 8. HTTP API

주소 `http://127.0.0.1:8080`. 인증은 `Authorization: Bearer <service token>`이다. token은 권한 제한 파일에 보관하며 인증 header로 전달한다.

| Method/path | 인증 | 성공 응답 |
|---|---|---|
| GET /healthz | 공개 | 200, `{"status":"alive"}` |
| GET /health | 공개 | 준비 후200, `{"status":"ready"}` |
| GET /readyz | 공개 | /health와 동일 |
| GET /version | Bearer | 200, 서비스 identity, 모드 계약, 제한 |
| POST /v1/generations | Bearer | 202, ID/상태/boot_id/duplicate |
| GET /v1/generations/{id} | Bearer | 200, job 상태 또는 완료 결과 |

health/ready의 준비 전 응답은503, `{"status":"not_ready"}`다. healthz의200은 프로세스 생존 상태를, health/readyz의200은 모델 준비 상태를 나타낸다.

### 8.1 GenerationRequest

| 필드 | 형식/필수 | 코드 제한 |
|---|---|---|
| request_id | string, 필수 | 길이1..128, `^[a-zA-Z0-9_.-]+$` |
| contract_id | string, 필수 | 소문자 hex64자리 + 실제 allowlist 존재 |
| user | string, 필수 | 길이2..60000; native JSON object를 문자열로 전달 |
| max_new_tokens | integer, 선택 | 기본384, 1..384; type=int만 허용 |

외피는 Pydantic strict이며 허용 필드는 위4개다. messages/system/model/adapter/execution_mode 등의 추가 필드는 거부한다. HTTP body 전체 상한65,536byte는 chunked request에도 적용한다.

native user는 순수 JSON object를 권장한다. 기존 STATE: 형식을 위해 runtime은 첫 STATE: 뒤를 파싱하므로 데이터 문장 안에 이 문자열을 포함하는 입력에는 주의가 필요하다. HTTP 서버는 native 객체와 입력 제한을 검사하며 계약별 내부 업무 schema는 별도 검증 대상이다. 실제 system/user 한 쌍의 native template token 수와 응답 예약 합이4096을 넘으면 입력 전체를 기준으로202 전에 거부한다.

| 용도 | contract_id |
|---|---|
| Qwen base 검색 제어 | `f2d9430c098d13096434f4100b1e507568c8b14da43b360592181e52e17593d3` |
| 기본 RC3 SourceReview bridge | `7240db117d7c66d5bb162ce72290fee4b87bfaefa97771246d392be07c0b0114` |
| bridge가 허용하는 parent | `4fe243c2300a5084f54833e7b6fd8aa45f55592c9dfcf6aaa53cc07692e0282f` |

그 외 기존 RC3 계약은 `/version`에서 확인할 수 있다. bridge.prepare의 허용 계약은 위 기본 SourceReview와 parent 두 종류다.

### 8.2 접수, 조회, 중복

새 접수 예:

```json
{"id":"a2bb2e7f-22ef-4c2f-9e51-528ebf67d0be","status":"running","boot_id":"6ded0350-ad57-4b92-932b-78d1668029ba","duplicate":false}
```

응답 Location은 `/v1/generations/{id}`다. 이 예는 기존 합성 검증의 식별자다. 현재 조회 가능 여부는 해당 boot의 유지 상태와 lookup TTL에 따른다.

준비된 서비스에서 동일 request_id와 동일 정규화 요청 외피를 다시 제출하면 기존 ID와 duplicate=true를 반환한다. body가 다르면409다. fingerprint에는 request_id 자체와 기본값이 채워진 max_new_tokens도 포함된다. 비교 기준은 user 문자열의 공백까지 반영한 정규화 외피의 정확한 일치다.

중복 조회는 busy 검사보다 앞서지만 준비 여부 검사보다 뒤다. job 조회와 idempotency는 boot 단위다. 서버 재시작 시 새 조회 registry를 사용하며 이전 결과는 보존된 증적 파일에서 확인한다.

running 반환 필드: id, request_id, status, created_at, boot_id. failed는 여기에 error=`generation_failed`를 더한다. fingerprint는 서버 내부 registry에서 관리한다. 완료 결과는 다음 표를 따른다.

### 8.3 완료 결과

| 필드 | 형식/설명 |
|---|---|
| id / request_id / status | job UUID / 요청 ID / completed |
| raw_text | special token 포함 원문 decode |
| text | skip_special_tokens=True로 decode한 문자열; 업무 JSON은 별도 검증 대상 |
| generated_token_ids | 생성 token ID 정수 배열 |
| execution_mode | memory_planner / rc3 |
| adapter_applied | planner=false, rc3=true |
| input_tokens / generated_tokens | 정수 token 수 |
| reserved_output_tokens | 요청의 응답 예약 |
| finish_reason | eos / length / other |
| ended_with_native_terminator | 마지막 token이 native EOS인지 bool |
| elapsed_seconds | runtime.generate 구간 시간; 전체 검색과 HTTP 왕복은 별도 측정 대상 |
| input_sha256 | 실제 system/user messages의 canonical hash |
| prompt_token_ids_sha256 | 입력 token ID 배열 canonical hash |
| rendered_sha256 | native 렌더링 문자열의 canonical JSON hash |
| output_sha256 | raw_text의 UTF-8 SHA256 |
| model_receipt_id / boot_id | 모델 release descriptor digest / 프로세스 실행 ID |
| output_repaired | false |

정상 종료 token은 `<|im_end|>` ID248046, pad ID248044다. finish_reason은 EOS 우선, 생성 길이가 예약 이상이면 length, 그 외 other 순서로 결정한다.

### 8.4 /version

반환 필드: service=`DoriLab RC3`, boot_id, pid, ready, phase, busy, model_receipt_id, contracts, limits. receipt ID는 로드 전 null일 수 있다. phase는 loading/ready/failed/stopping이다. contracts 각 항목의 필드는 id/route/system_sha256이다. prompt 본문은 서버가 관리한다. limits는 max_total_tokens/max_new_tokens/max_retained_jobs/result_ttl_seconds다.

### 8.5 HTTP 오류

| 상태 | 의미 | 호출자 처리 |
|---|---|---|
| 401 | Bearer header 누락 또는 형식 불일치 | token 전달 방식 확인 |
| 403 | token 불일치 | 승인된 token 파일 확인 |
| 404 | 해당 boot의 미등록/만료 job | 저장한 boot와 ID 확인 후 재제출 판단 |
| 409 | 같은 request_id로 다른 body | 원래 요청 확인 |
| 413 | body byte 상한 초과 | 입력 구성 수정 |
| 422 | 외피 schema, 미등록 계약, native 입력 또는 token 예산 오류 | 원문을 고치거나 근거 선택 수를 명시적으로 조정 |
| 429 | generation busy 또는 boot 누적256 job 한도 | busy는 Retry-After:1; 재시도는 호출자가 결정 |
| 503 | 준비 전/실패, 또는 Uvicorn HTTP 동시 연결 한도32 초과 | health/ready 및 운영 상태 확인 |

직접 발생시키는 오류는 보통 `{"detail":"..."}`다. Pydantic/FastAPI validation detail은 배열일 수 있다. Uvicorn 과부하 응답은 별도 형식으로 처리해야 한다. 저장 I/O 예외 등에는500도 가능하다.

## 9. CLI 계약

기본 형식은 `python -m project_memory --store <directory> --project <id> <command>`다. 두 전역 인자는 필수이며 subcommand 앞에 둔다.

| command | 필수 인자 | 선택 인자 | stdout 결과 |
|---|---|---|---|
| insert | file | --expected-version | insert 반환 객체 |
| manifest | — | — | manifest 객체 |
| inspect | trajectory_id | --start=0, --stop | step span |
| withdraw | trajectory_id, --expected-version | — | version 객체 |
| query | packet file | 공통 검색/제어 옵션 | evidence bundle |
| prepare | packet file, --output | 공통 옵션 + 준비 옵션 | receipt만 출력; 파일에 request/memory/receipt 저장 |
| generate | packet file, --token-file, --output-dir | 공통 옵션 + 준비 옵션 + --base-url | 최종 기억-생성 receipt |

공통 검색/제어 옵션:

| 옵션 | 기본값/동작 |
|---|---|
| --top-k | 6 |
| --max-bytes | 12000 |
| --queries-file | 생략 시 전체 pool에 원 질문 |
| --controller | qwen; 선택 off/rules/qwen |
| --planner-url | http://127.0.0.1:8080 |
| --planner-token-file | /root/.config/dorilab/inference.token |
| --planner-trace-dir | 생략 시 `<store>/_planner_traces/<UUID>`; 명시 경로는 새 디렉터리 |
| --controller-timeout | 90초 |

준비 옵션: --contract-id(§8의 기본 bridge ID), --max-new-tokens=384, --native-check(기본false). --native-check는 기존 CPU processor로 실제 token 수를 센다. Mac에서는 일반적으로 생략하고 서버 검사를 사용한다.

generate의 --base-url 기본값은 http://127.0.0.1:8080이다. planner URL/token과 최종 reviewer URL/token은 별개 옵션이다. Mac에서 둘 다 올바르게 지정해야 한다. --output과 --output-dir에는 새 파일/디렉터리 경로를 지정해야 하며 기존 경로는 오류로 처리한다.

CLI 실패는 nonzero exit와 Python/argparse 오류로 전달한다. query와 prepare도 기본 controller=qwen이면 실제 GPU job을 생성한다. 로컬 검색 모드는 --controller off 또는 rules로 선택한다.

## 10. 증적 파일

| 위치 | 내용 |
|---|---|
| `<store>/<project>/state.json` | 원본, revision, 활성 mapping |
| `<planner_trace>/<순번>/request.json` | 고정 planner 계약과 context |
| 같은 경로/service_version.json | 계획 제출 전 실행 identity |
| 같은 경로/accepted.json | 접수 성공 시202 결과 |
| 같은 경로/result.json | terminal 상태까지 도달한 경우 원문 결과 |
| `<review_output>/preparation.json` | request/memory/receipt |
| 같은 경로/service_version.json, accepted.json, result.json | reviewer HTTP 단계 증적 |
| 같은 경로/memory_generation_receipt.json | 성공한 memory→model 연결 |
| 같은 경로/failure.json | 제출, poll try 구간 예외 유형과 재제출 주의 문구 |
| `inference/run/<boot_id>/<job>.input.json` | 요청, 입력 hash, prompt token IDs, boot_id |
| `inference/run/<boot_id>/<job>.json` | completed 또는 failed 결과 |
| 같은 경로/model_receipt.json | 로드된 모델, adapter, shard 검증 descriptor |
| 같은 경로/boot.json, warmup.json, planner_warmup.json, ready.json | 프로세스, 기술 준비 증적 |

증적 파일은 완료된 처리 단계에 따라 생성된다. token/사전 identity 검증은 접수 전에 수행하며 accepted/result 파일은 각각 접수 응답 수신과 terminal 조회 후 저장한다. POST 이후 연결 종료 시 request 파일만 남아도 서버의 job은 실행 중일 수 있으므로 서버 측 접수 상태를 확인해야 한다.

## 11. Hash 규약

기억 계층 canonical JSON은 Python의 ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False 설정이다. sealed runtime common.digest도 같은 규약을 사용한다.

| 값 | hash 대상 |
|---|---|
| source_hash | trajectory 전체 canonical JSON |
| memory version | version key 제거 후 snapshot canonical JSON |
| evidence_id | `[project, source_hash, pool, index]` canonical SHA256의 앞32자리 + MEM- |
| bundle_hash | bundle_hash/cache_hit key 제거 후 bundle canonical JSON |
| plan_sha256 / span_sha256 | 파싱한 plan / inspect span canonical JSON |
| contract_id | 고정 system prompt 원문 UTF-8 |
| user_sha256 | 실제 user 문자열 UTF-8 |
| rendered_sha256 | 렌더링 문자열을 JSON 문자열로 직렬화한 canonical bytes |
| output_sha256 | raw_text 원문 UTF-8 |

controller bundle_hash에는 elapsed_seconds가 포함되므로 같은 질의도 실행마다 hash가 달라질 수 있다. 모델 receipt는 boot_id key 제거 후 release descriptor의 digest다. 소스 전체의 변경 이력은 별도 SOURCE_BASELINE.json으로 추적한다. hash는 무결성 비교에 사용하며 접근 제어와 서명에는 별도 구성이 필요하다.
