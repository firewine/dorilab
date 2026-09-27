# LongMemEval-V2 기반 프로젝트 기억 초기 적용 결과

검증일: 2026-09-27 UTC. 상태: **초기 적용 및 RunPod 내부 HTTP 연결 검증 완료**.

## 적용 내용

[LongMemEval-V2 §4](https://arxiv.org/html/2605.12493v1#S4)의 AgentRunbook 구성을 참고해 실행 가능한 `project_memory` 모듈을 추가했다.

| 기능 | 구현 결과 |
|---|---|
| 원본 보존 | trajectory의 관찰 시각, 원문, action, source URI/revision과 canonical 내용 hash 보존 |
| 세 기억 pool | raw 관찰 / before-action-after 사건 / confirmed 작업·gotcha·premise 메모 |
| 근거 수집 | 프로젝트 및 unit/configuration/run 일치 필터 → pool별 BM25 검색 → whole-record 선택 |
| 원문 검사 | manifest와 step 구간 inspect, 별도 WORKFLOW_KO.md |
| 개정 | expected_version 비교 후 교체, 이전 revision 보존, 활성 revision만 검색 |
| 철회 | 활성 검색에서 제외하고 다음 조회부터 이전 캐시 적중 차단; 물리적 삭제는 아님 |
| 캐시 | 프로젝트·snapshot·scope·질의·선택 예산별 bounded LRU, 기본64개 |
| 권한 경계 | trusted AccessScope 검사 후 파일/캐시 접근; 로컬 운영자 CLI |
| RC3 연결 | 기존 SourceReview observations에 근거 추가 → 동일 계약과 native template로 HTTP 호출 |
| 결과 보존 | 준비된 입력, 근거 receipt, 202 ID, 결과 원문, model receipt, boot_id 기록 |

추론 서버 코드, GPU 모델, adapter, bootstrap, Start Command, 기존 학습/평가 결과는 변경하지 않았다. 추가 패키지 설치나 모델 재시작 없이 기존 API를 사용했다. 문서에서 새 클라이언트를 찾을 수 있도록 inference/API_CONTRACT.md에 연결 설명을 추가했다.

## CPU 검사

`python -m unittest project_memory.test_memory -v`: **21개 통과**.

- static: 원시 관찰과 출처 step 재조회
- dynamic: before/action/after와 시각 보존, 인과관계 추정 금지
- workflow/gotcha: 관련 confirmed 메모 검색과 원문 연결
- premise: 다른 scope 배제, 관련 전제 메모 조회, 알려지지 않은 질의에 근거 없음 반환
- 프로젝트 격리와 권한 변경 후 cache 접근 거부
- 재실행 후 저장 데이터 읽기, 동일 삽입 중복 방지
- 개정 CAS, 다른 로컬 프로세스에서 갱신 후 cache 무효화
- 철회 반영, 후보 메모 제외, LRU 용량과 반환 객체 격리
- 동시 로컬 writer 4개 삽입 유실 없음
- 입력 검증, 경로 이탈, snapshot 변조 검출
- 입력 token 예산 초과 거부, timeout 시 ID 보존과 자동 재제출 금지
- 모델의 잘못된 JSON도 mock 출력 원문 그대로 보존

로그: `artifacts/20260927_memory_v1/cpu_tests.log`

## 실제 HTTP 검증

새 합성 프로젝트 `synthetic-lme-v2`를 `/workspace/dorilab/memory_data`에 생성했다. 합성 trajectory 한 개에서 raw 2개, event 1개, note 3개가 생성됐고, query에서 3개 근거를 선택했다. 학습 정답이나 기존 benchmark 입력을 사용하지 않았다.

| 항목 | 실제 결과 |
|---|---|
| native 입력 토큰 | 1,753 |
| 응답 예약 | 384 |
| 생성 토큰 | 56 |
| 생성 지연시간 | 5.661968초; 검색/CPU processor 준비 시간을 포함한 end-to-end 지연시간은 아님 |
| 종료 | eos, native 종료 토큰 확인 |
| 접수/결과 | HTTP 202 → GET completed |
| JSON 출력 | 원문 파싱 가능; 자동 교정 없음 |
| 근거 추적 | 반환한 evidence_refs가 실제 검색·전달된 기억 ID에 포함 |
| 상태 | /health 200, /readyz 200 |
| boot_id | `55aae728-3b58-4e0a-bbbb-21f8d5d38e93` |
| job_id | `6409b5af-da8f-45f9-ad72-b5b4aa2a019c` |
| model receipt | `bfcd7d5ea65053ee9f6b57d69cbe51d698087cfdc328525a47c40f7d92d5c851` |

모델 원문을 파싱한 결과:

```json
{"action":"NO_ACTION_REQUIRED","claim_id":"SYN-MEMORY-01","evidence_refs":["MEM-77a2687584ce0260542f7b0a806abcf7"]}
```

이는 합성 입력 존재 여부 질문에 대한 연결 결과다. 공학 적합성, 프로젝트 승인, 일반화 점수 또는 공식 LongMemEval-V2 성능을 의미하지 않는다.

증적 디렉터리: `artifacts/20260927_memory_v1/http_smoke/`

- `preparation.json`: 선택한 기억, 원본 출처, 요청과 입력 hash
- `accepted.json`: 202 job ID와 boot_id
- `result.json`: 종료 토큰 포함 raw_text, token IDs/count, finish_reason, 지연시간, 입출력 hash
- `service_version.json`: 제출 전 서버 identity와 제한
- `memory_generation_receipt.json`: 기억 snapshot과 모델 결과 연결
- `verification.json`: hash·token·출처·health 검사 결과

CPU processor 초기화 시 기존 Transformers의 `image_like_kwargs` docstring 진단이 출력됐다. 해당 패키지는 수정하지 않았으며 native 토큰 검사와 HTTP 생성은 정상 완료됐다.

## 범위와 남은 제약

이 적용은 CLI/라이브러리에서 명시적으로 사용하는 초기 기억 계층이다. 기존 모든 HTTP 요청에 자동으로 기억을 삽입하지 않으며, 새로운 다중 사용자 기억 API를 노출하지 않는다.

검색은 추가 모델 없는 lexical BM25+한국어 bigram이다. 논문의 dense retrieval, LLM multi-query controller, 자동 coding-agent 검색, 멀티모달 근거 수집을 재현하지 않았다. 해당 기능을 RC3의 검증되지 않은 추가 역할로 가정하지 않았다.

파일 저장소는 단일 호스트용으로 32MiB/1000 revision 제한을 둔다. 여러 Pod가 같은 파일에 동시에 쓰는 배포는 지원하지 않는다. /workspace 공유 볼륨의 권한만으로 프로젝트 기밀성을 보장하지 않는다. 실제 다중 사용자 배포는 외부 DB와 인증 계층이 필요하다. `withdraw`는 감사 이력을 남기는 철회이며 영구 삭제가 아니다.

Mac/Docker 실기 연결은 아직 시험하지 않았고 RunPod 내부 연결만 검증했다. 실행 예시와 Mac 적용 방법은 [README_KO.md](README_KO.md)에 있다. 서비스는 기동 상태를 유지한다.
