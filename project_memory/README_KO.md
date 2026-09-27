# DoriLab 프로젝트 기억 v1

실행 가능한 초기 적용이다. 별도 설치 패키지 없이 Python 표준 라이브러리로 원시 관찰(raw), 기록된 상태 변화(events), 절차·함정·전제 메모(notes)를 관리하고 기존 SourceReview HTTP 서비스로 연결한다.

근거: [LongMemEval-V2 논문 §4](https://arxiv.org/html/2605.12493v1#S4). 세 pool과 context-gathering 인터페이스는 AgentRunbook-R, 파일 보존·manifest·구간 inspect·작업 지침은 AgentRunbook-C를 참고했다. 논문 구현의 재현 또는 공식 벤치마크 통과를 뜻하지 않는다. 검색은 BM25+한국어 bigram이며 상주 Qwen의 base 모드를 사용하는 검색 제어기를 추가했다. [제어기 사용법과 제한](CONTROLLER_KO.md)을 참고한다. dense embedding, 임의 coding-agent 실행, 이미지 검색은 구현하지 않았다. RC3를 범용 기억 추출기로 사용하지 않는다.

## 동작과 적용 범위

- `insert`: 구조화된 trajectory 원본을 보존한다. 입력과 hash가 같으면 중복 삽입하지 않는다.
- `manifest`: 활성 source revision, scope, 각 pool 수량과 snapshot version을 반환한다.
- `inspect`: 활성 trajectory의 지정 step 구간을 원문으로 반환한다.
- `query`: 프로젝트와 unit/configuration/run scope를 먼저 필터링한 후 pool별 검색 결과를 합친다. pool별 다른 질의는 `--queries-file`로 지정한다.
- `prepare`: 기존 SourceReview observations에 선택한 근거만 추가한다. system prompt와 모델 설정은 유지한다.
- `generate`: 준비된 입력을 기존 `/v1/generations`로 한 번 제출하고 결과를 조회한다. 입력·202 ID·모델 출력·기억 근거 receipt를 저장한다.
- `withdraw`: 활성 검색에서 trajectory를 철회한다. 감사용 revision은 보존한다. 물리적 삭제 기능은 아니다.

각 raw 관찰에는 시각과 step 번호가 있다. event는 연속된 관찰 사이에 기록된 action과 before/after를 담으며 인과관계나 작업 성공을 추정하지 않는다. note는 원본 step 번호를 필수로 가지며 `confirmed`만 검색된다. 이 상태는 신뢰된 입력 작성자의 검토 표시이지 시스템의 진실성 보증이 아니다. 모델 답변은 자동으로 기억에 추가되지 않는다.

source_hash는 **입력 trajectory 전체를 canonical JSON으로 직렬화한 SHA256**이다. URI에 있는 외부 문서 전체를 다운로드·검증한 hash라고 주장하지 않는다. evidence ID에는 프로젝트와 이 hash가 포함된다. 원문 출처를 바꾸면 새 revision을 작성해야 한다.

## 실행 예시 — RunPod

프로젝트 루트에서 실행한다. 아래 입력은 새로 만든 합성 예시이며 학습 자료나 benchmark gold를 사용하지 않는다.

```bash
cd /workspace/dorilab
/root/venvs/dorilab-tournament/bin/python -m project_memory --store /workspace/dorilab/memory_data --project demo-memory insert project_memory/examples/trajectory.json
/root/venvs/dorilab-tournament/bin/python -m project_memory --store /workspace/dorilab/memory_data --project demo-memory manifest
/root/venvs/dorilab-tournament/bin/python -m project_memory --store /workspace/dorilab/memory_data --project demo-memory query project_memory/examples/packet.json --top-k 3 --max-bytes 6500
/root/venvs/dorilab-tournament/bin/python -m project_memory --store /workspace/dorilab/memory_data --project demo-memory generate project_memory/examples/packet.json --top-k 3 --max-bytes 6500 --native-check --token-file /root/.config/dorilab/inference.token --output-dir /workspace/dorilab/project_memory/artifacts/manual-http-01
```

output-dir는 새 경로여야 한다. 토큰 값은 인자·로그·receipt로 출력하지 않는다. `--native-check`는 기존 CPU processor만 읽고 GPU 모델을 로드하지 않는다. 생략하면 기존 서버가 202 전에 정확한 token 수를 검사한다. `max-bytes`는 검색 근거 선택 예산이며 token 수의 추정치가 아니다. 선택 제외 목록을 반환하며 개별 근거 텍스트는 자르지 않는다. 입력+응답 예약 4096, 응답 최대384의 기존 제한은 그대로다. 초과한 요청은 422 또는 로컬 오류로 거부한다.

준비만 하려면 `generate` 대신 `prepare ... --output 새파일.json`을 사용한다. 해당 파일의 `request` 객체는 기존 Mac client의 `--request-file` 형식과 같다. `memory`와 `receipt`를 API body에 넣으면 안 된다. 전용 `generate` 명령은 이를 분리하고 출처 증적을 함께 보존한다.

## 개정, 격리와 캐시

기존 trajectory를 변경하려면 source.revision을 바꾸고 현재 manifest.version을 `insert --expected-version <version>`으로 전달한다. 오래된 snapshot을 기준으로 덮어쓰려 하면 거부한다. 활성 revision만 검색하며 이전 revision은 같은 state.json에 감사용으로 보존한다. 별도 실행으로 다시 읽어도 데이터가 유지된다.

검색 캐시는 인스턴스당 기본64개 LRU다. key에는 프로젝트, snapshot version, 질문, scope, pool별 질의, 선택 예산이 포함된다. 매 조회마다 현재 snapshot을 읽으므로 다른 로컬 프로세스의 삽입·개정·철회도 다음 조회에 반영된다. 프로세스 종료 시 캐시는 사라지고 영구 기억으로부터 재생성된다. 응답 의미 캐시와 요청 간 GPU KV 공유는 추가하지 않았다.

AccessScope는 신뢰된 인증 계층이 부여해야 한다. 권한 검사는 디스크 읽기와 cache lookup 이전에 수행한다. **CLI는 파일 접근 권한을 가진 로컬 운영자용이며 새로운 다중 사용자 HTTP 권한 시스템이 아니다.** 운영 UI/API에 연결할 때 인증된 사용자→허용 프로젝트 매핑을 먼저 구현해야 한다. 허용 프로젝트를 사용자 body에서 그대로 만들면 안 된다.

## 저장소와 배포 제한

초기 저장소는 프로젝트당 `state.json` 하나를 임시 파일→fsync→atomic replace로 교체한다. snapshot checksum을 읽을 때마다 검사한다. 동일 호스트의 프로세스들은 `/tmp/dorilab-memory-locks-UID`의 flock으로 직렬화한다. **같은 저장소에 여러 Pod/호스트가 동시에 쓰는 구성은 지원하지 않는다.** 파일시스템이 제공하는 rename/fsync 이상의 전원 장애 내구성을 보장하지 않는다.

프로젝트당 총32MiB/1000 revision, trajectory당100 step/30 note/512KiB로 제한한다. 한도에 도달하면 거부하고 자동 삭제하지 않는다. 현재는 작은 프로젝트를 위한 bounded scan이며 대규모 데이터는 외부 영구 DB·검색 인덱스로 옮겨야 한다.

`/workspace`는 프로젝트 기억을 Pod 재생성 뒤에도 유지하기 위한 위치다. 공유 Network Volume의 권한 특성상 비밀 저장소로 취급하면 안 된다. 실제 프로젝트 데이터의 접근 경계는 배포 계층에서 확보해야 한다. SQLite WAL을 이 네트워크 볼륨에 생성하지 않는다. [SQLite 제약](https://www.sqlite.org/wal.html)

Mac에서도 `project_memory` 폴더를 앱 코드와 함께 두고 Python 3.10+로 같은 CLI를 실행할 수 있다. `--store`는 Mac 영구 로컬 디렉터리, `--base-url`은 기존 SSH 터널의 loopback 주소, `--token-file`은 Mac에 안전하게 교환된 토큰 경로를 지정한다. Mac에서는 `--native-check`를 생략하고 서버 검사를 사용한다. Docker는 코드와 기억 디렉터리를 각각 mount하고 token은 secret으로 제공한다. 현재 Mac/Docker 실기 연결은 검증하지 않았다.

## 검증

```bash
PYTHONDONTWRITEBYTECODE=1 /root/venvs/dorilab-tournament/bin/python -m unittest project_memory.test_memory -v
```

합성 CPU 테스트는 LME-V2의 static/dynamic/workflow/gotcha/premise 범주를 참고한 회귀 검사다. 기억 검색/격리와 데이터 경로를 검사하며 공식 LME-V2 정답률이나 RC3 공학 정확도 평가가 아니다. wrong premise 테스트는 관련 메모 조회와 근거 없음 처리를 확인하며 범용 자연어 전제 판별기를 구현했다고 주장하지 않는다.

초기 저장·검색 적용 결과는 `IMPLEMENTATION_REPORT_KO.md`, 이후 Qwen 검색 제어기와 서비스 적용 결과는 [CONTROLLER_REPORT_KO.md](CONTROLLER_REPORT_KO.md)에 기록한다. 제어기 계약을 활성화하기 위해 추론 프로세스를 한 번 교체했으며 Pod 재시작·학습·모델 재다운로드·전체 benchmark 실행은 하지 않았다.
