# 복구 RunPod 실행환경 승인·적용 결과

작성일: 2026-10-09. 대상: `205.196.144.74:11284`, Mac Docker 앱 `http://localhost:18000`.

현재 상태는 **LIVE / READY**다. 사용자 승인 “검증된 0.23.3 실행환경 승인”을 받은 뒤 새 model receipt를 로컬 기준에 등록하고 API/worker를 재빌드했다. 인증된 실제 `/version`이 승인값과 정확히 일치하며 브라우저의 **Local LLM LIVE 자동 시연 시작** 버튼이 활성화됐다.

## 차이와 반영 범위

이전 receipt: `b96e72897a27c3a6a0eee4db7c04d55efba10bbd373efe0a83f56221d8a2a847`.

새 receipt: `7e8f301cdbe9511d4e6b108a3b8bc8ae7330b59a59b7d3dfcb69296c66bb4f0a`.

boot_id를 제외한 model receipt의 차이는 `runtime.tokenizers 0.23.2 → 0.23.3`이다. base revision·18 shard·adapter weight/config·native tokenizer/template asset hash·활성 RC3 contract·generation policy는 동일했다. 실제 GPU interpreter의 설치 metadata와 native 파일 8개의 SHA256도 대조했다. 실제 실행 Python은 `/root/venvs/dorilab-tournament/bin/python`이다.

`packages/contracts/model_profiles/rc3.json`은 `model_receipt_id` 하나만 변경했다. worker의 exact receipt·contract·예산 검사는 유지한다. 이전 receipt와 알 수 없는 receipt를 계속 차단하는 회귀를 추가했다. 서버 패키지 설치·모델 교체·Pod 변경·Site/Render/Neon 배포는 없었다.

## 실제 실행 검증

기존 공개 합성 입력 세 건을 현재 RunPod에서 각각 한 번 생성했다. 원출력을 저장한 뒤 strict Validator와 기존 사례 계약을 대조했다. 실행 모드는 **LIVE_SYNTHETIC_ONLY**이며 REPLAY나 mock 결과가 아니다.

| 사례 | 실제 action | 입력 / 생성 token | 결과 |
|---|---|---|---|
| 입력 근거 부족 | REQUEST_EVIDENCE | 948 / 48 | 통과 |
| 한정된 입력 근거 존재 | NO_ACTION_REQUIRED | 1055 / 34 | 통과 |
| 다른 형상의 근거를 전용 | CHALLENGE | 1060 / 46 | 통과 |

세 사례의 input token 수·prompt token ID hash·rendered hash가 이전 승인 사례와 같았다. EOS 종료, 응답 예약 384, 전체 4096 예산, request/boot/model receipt, output hash와 실제 token ID 수를 확인했다. 원출력 교정이나 실패 후 재생성은 없었다. NO_ACTION_REQUIRED는 해당 BM1 입력 근거 범위의 결과이며 제품 성능 적합성이나 공식 종결 승인이 아니다. 이 세 건은 제한된 연결·출력 계약 검사이며 모델 정확도 전체 평가를 뜻하지 않는다.

| 로컬 검사 | 결과 |
|---|---|
| 승인 전 격리 PostgreSQL/mock 전체 회귀 | **235 passed / 1 warning / 43.52초** |
| 최종 승인 profile 이미지 관련 회귀 | **21 passed / 1 warning / 2.59초** |
| 실행 중 worker의 `/healthz`·`/readyz`·Bearer `/version` | 모두 **200** |
| 실행 중 worker exact receipt 검사 | 오류 목록 `[]`, DB remote 상태 **READY** |
| 브라우저 새로고침 → 자동 시연 모드 창 | **App LIVE · Remote READY**, LIVE 시작 버튼 활성화 |
| 적용 전/후 기존 DB 건수 | 프로젝트 5, 첨부 28, ReviewJob 24, ModelRun 24, 사람 결정 5 유지 |
| 실제 첨부 bytes 크기·SHA256 | **28/28 일치** |

warning은 기존 Starlette testclient anyio alias deprecation이다. 전체 회귀는 승인 전 후보를 격리한 상태에서 실행했고, 최종 승인 profile이 들어간 이미지에서는 `test_contracts.py`와 `test_local_connection_apply.py`를 다시 실행했다. 테스트는 업무 DB와 분리된 `dorilab-test` DB에서 수행했다.

적용 직전 진행 중인 검토는 0건이었다. API/worker만 재생성했으며 DB·migration·tunnel·원격 GPU 프로세스는 유지했다. 검증한 boot은 `e8b499c1-766f-4589-b487-144fbb9116d8`이다. 적용 과정의 generation은 0건이고 앞선 합성 검사 3건은 업무 Job으로 만들지 않았다. 업무 테이블 전체 digest 비교나 down/up 전체 복원 시험을 이번에 추가 수행한 것은 아니다.

## 변경 파일과 증거

- `packages/contracts/model_profiles/rc3.json`: 승인된 receipt 하나 등록.
- `tests/test_contracts.py`: 후보 등록을 격리해 검증하고 이전·미등록 receipt 차단 확인.
- `reference/runpod/inference/receipts/release-7e8f301c/`: 새 receipt, 실제 합성 출력 3종, conformance, runtime 조사, 명시적 승인 PROMOTION 기록. `release-b96e7289/`는 보존.
- `README_LOCAL_DOCKER.md`, `docs/STATUS.md`, `docs/STATUS.json`, 승인 계획·연결 수정 보고서와 이 문서: 최신 READY 결과와 과거 시험 구분.

실행 기록은 `var/run-records/runtime-alignment-20261009/`에 보존했다. 핵심 파일은 `CONFORMANCE_RECEIPT.json`, `PROMOTION.json`, `local_status.json`, `artifact_verification.json`, `approved-baseline-tests.log`, `applied-profile-tests.log`, `local-build.log`와 READY 화면이다. token·개인키·DB 암호는 포함하지 않는다.

실행 환경: macOS 27.0.1 arm64, Docker `desktop-linux`, Engine 29.8.0, Compose 5.5.1, Linux container aarch64. Docker context는 그대로다.

## 실행 방법과 미검증 범위

현재 앱에서 새로고침 → **자동 시연** → **Local LLM LIVE 자동 시연 시작**을 누른다. 같은 실행을 보려면 **Blackboard 관찰 창 열기**를 먼저 누른다. LIVE 시작은 새 합성 설정과 실제 모델 요청을 만들며 사람 승인·공식 종결 앞에서 멈춘다.

개발을 다시 시작할 때는 기존 `./scripts/dev.sh up`을 사용한다. 주소·외부 SSH 포트 변경은 **RunPod 연결 → 저장 · LIVE 연결**로 적용한다.

승인 적용 후 전체 자동 시연·사람 결정 경로를 새로 실행하지 않았다. 이번 작업은 로컬 연결의 runtime mismatch 해소이며 Site의 배포 기준을 함께 변경한 것은 아니다. 새 서버가 다른 receipt를 제공하면 기존 검사가 다시 차단하며 별도 실제 검증·승인이 필요하다.
