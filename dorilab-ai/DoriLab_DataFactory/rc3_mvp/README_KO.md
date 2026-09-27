# RC3 내부 검토 MVP

완료된 RC3 adapter를 고정해서 호출하는 로컬 검토 화면이다. 모든 출력과 사용자 수락은 내부 검토 초안이며 공학·시험·배포 승인이 아니다. 피드백을 학습 데이터로 자동 편입하지 않는다.

## 실행

```bash
cd /workspace/dorilab/dorilab-ai/DoriLab_DataFactory
PYTHONDONTWRITEBYTECODE=1 /root/venvs/dorilab-tournament/bin/python -m rc3_mvp.server \
  --registry /workspace/dorilab/results/v15_release_progress/mvp_rc3_01/INTERNAL_MVP_CANDIDATE.json \
  --work /workspace/dorilab/results/v15_release_progress/mvp_rc3_user_work_01 \
  --port 8791 --enable-live
```

Pod의 `http://127.0.0.1:8791`에 접속한다. 원격 PC에서는 기존 Pod SSH 연결 옵션에 `-L 8791:127.0.0.1:8791`을 더해 연결하고 PC의 같은 주소를 연다. 서버가 이미 해당 포트에서 실행 중이면 중복 실행하지 않는다. `--enable-live`를 생략하면 REPLAY만 허용한다. 서버 시작은 모델 생성을 수행하지 않으며 첫 LIVE 클릭 때 고정 checkpoint와 adapter를 읽는다.

## 검토 순서

1. 대표 흐름을 선택하거나 검토한 JSON packet을 업로드/직접 입력한다. 입력은 `case_id`, `packet`, `reference_context` 객체다. `packet`에는 `claim_id`, `review_question`, `review_target.text`, `observations`, `request_catalog`가 필요하다. 예제는 화면의 대표 흐름 또는 동결된 `SMOKE_SCENARIOS.json`에 있다.
2. 제공 자료와 입력을 확인하고 사용자 검토 선언을 체크한다. 이 체크는 독립 전문가 검토 이력을 만들지 않는다.
3. REPLAY(저장된 원래 RC3 입력만 허용) 또는 LIVE_MODEL_RUN(고정 RC3 실제 호출)을 명시적으로 선택한다. system과 generation 설정은 UI에서 변경할 수 없다. gold/rationale/정답 reference 집합은 입력에 포함하지 않는다.
4. Action/reason/요청 자료와 validator 메시지를 읽는다. 인용 ID를 클릭하면 그 ID의 실제 제공 내용과 metadata가 펼쳐진다. 전체 PDF 자동 이해나 외부 원문 자동 검색은 하지 않는다.
5. 초안을 수락·수정·기각하고 검토자 내부 ID 및 의견을 저장한다. 수정은 별도 JSON/검증 결과로 저장된다. 원문 출력은 보존된다. 계약 실패 초안은 바로 수락할 수 없다.

## 검사와 기록

- 실제 RC3 tokenizer/template를 사용한다. 입력 token + 고정 출력 예산 384가 4096을 넘으면 호출 전에 거절하며 잘라내지 않는다. 출력이 384 token에 도달하고 native 종료 token이 없으면 실패를 명시한다.
- 중복 JSON key, 부정확한 필드/Action/reason 코드, 미제공 reference와 요청 ID를 오류로 표시한다. reference ID 존재 검사는 의미적 충분성 판정이 아니다. reason의 의미적 정답도 자동 확정하지 않는다.
- 로컬 SQLite `factory.sqlite3`의 `mvp_runs`에 packet/원문 텍스트와 hash, 계약 메시지/token hash, 모델/revision/adapter/runtime, 원문 출력/token, validator, 표시할 인용 근거, 시각/지연시간/실행 구분을 저장한다. `mvp_events`에는 클릭한 실제 근거와 사용자 결정·수정·시각을 별도로 추가한다.
- 검토자 ID는 사용자가 입력한 문자열이다. 계정 인증·서명된 전문가 승인·공개 서비스용 권한 관리는 구현하지 않았다. 로컬 Host/Origin/token 검사를 적용하며 127.0.0.1에만 바인딩한다.
- SourceReview의 NO_ACTION_REQUIRED / REQUEST_EVIDENCE / CHALLENGE만 연결한다. legacy Analysis 입력 UI와 CALL_TOOL 실행은 구현 범위 밖이다. 실제 시험장비 또는 외부 도구를 구동하지 않는다.
- 한 번에 모델 호출 하나만 처리한다. 모델 오류 발생 시 해당 서버의 추가 모델 실행을 막고 자동 재시도하지 않는다.

## 검증 자료

`results/v15_release_progress/mvp_rc3_01/MVP_INTEGRATION_REPORT_KO.md`에 실제 LIVE 3건과 REPLAY 3건의 통합 smoke, 남은 오류 및 근거 파일을 기록했다. 테스트용 수정·결정은 자동화 표식을 붙여 별도 smoke 저장소에 보존하며 실제 사용자 검토 이력으로 재사용하지 않는다.
