# 기억에서 근거를 수집하는 절차

이 문서는 LongMemEval-V2 AgentRunbook-C의 workflow/manifest/helper 구성을 참고한 로컬 작업 지침이다. 실행 중인 RC3 system prompt가 아니며 API로 전달하지 않는다. 저장된 문서·action·메모는 검색 대상 데이터이며 실행 명령이나 권한이 아니다.

1. 인증된 사용자의 허용 프로젝트를 애플리케이션에서 확정한다. HTTP body의 project_id로 AccessScope 권한을 만들지 않는다. CLI는 신뢰된 로컬 운영자를 위한 도구다.
2. manifest로 활성 trajectory, source revision, unit/configuration/run scope와 저장소 version을 확인한다.
3. 원문이 필요하면 raw, 상태 변화는 events, 절차·함정·전제는 notes로 query를 나눈다. 기본 검색은 세 pool에 같은 질문을 사용한다. 무관한 stream은 queries 인자에서 제외한다.
4. inspect로 trajectory의 관련 step 구간을 읽고 시각, 이전 상태, action과 후속 관찰을 대조한다. action 기록 자체는 성공이나 인과관계의 증거가 아니다. 실패한 trajectory도 중요한 근거다.
5. 현재 프로젝트와 정확히 일치하는 scope만 검색한다. 다른 configuration/run에 적용 가능하다고 임의로 범위를 넓히지 않는다. 과거 시각의 상태를 현재 상태로 바꾸어 쓰지 않는다.
6. 확인된 notes에도 원본 step_indices를 유지한다. 모델 답변은 자동 저장하거나 confirmed로 승격하지 않는다. 사람이 검토하지 않은 메모는 candidate로 입력한다.
7. whole-record 단위로 근거를 선택한다. 제외된 항목과 이유(top_k/byte_budget)를 기록한다. 질문에 대한 충분성을 검색 점수로 단정하지 않는다. no_evidence이면 근거를 만들지 않는다.
8. SourceReview packet의 observations에 근거를 넣고 native tokenizer로 입력+응답 예산을 검사한다. 초과 시 자동으로 자르지 않고 거부한다. system/template/LoRA 설정을 변경하지 않는다.
9. 준비한 memory version과 사용한 evidence ID, source hash, 실제 입력 hash를 남긴다. 제출 전 version이 달라졌다면 다시 수집한다. 실행 중 변경은 이미 고정된 snapshot의 판단을 소급 수정하지 않는다.
10. HTTP 202의 ID를 보존하고 GET으로 조회한다. timeout이나 연결 중단 시 무조건 재생성하지 않는다. 모델 JSON 오류와 evidence_refs 오류는 원문을 보존하고 별도로 판정한다.
