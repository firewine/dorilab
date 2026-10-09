# 복구 RunPod runtime 승인 계획

대상: `205.196.144.74:11284`, 로컬 앱 `http://localhost:18000`.

**결과: 승인·적용 완료.** 사용자의 “검증된 0.23.3 실행환경 승인”에 따라 아래 계획을 실행했다. 후보 기록은 별도 승인 release로 보존하고, 로컬 profile 한 항목 변경과 API/worker 재빌드 뒤 **LIVE / READY** 및 LIVE 시작 버튼 활성화를 확인했다. [최종 결과](RUNPOD_RUNTIME_ALIGNMENT_RESULT_20261009.md). 아래의 승인 대기 설명은 승인 요청 당시 상황이다.

승인 요청 당시 상태는 **후보 검증 완료 / 승인 기준 변경 대기**였다. 자동 승인 검토가 명시적 승인을 요구해 기준 변경을 차단했다. 당시 실행 컨테이너는 기존 기준을 유지했고, 작업 중 수정했던 로컬 profile도 변경 전 bytes로 복원해 새 실행환경 자료를 `reference/runpod/inference/receipts/candidate-7e8f301c/`에 격리했다. 명시적 사용자 승인 이후 기존 차단 사유가 충족되어 적용 명령이 승인·실행됐으며, 자료는 `reference/runpod/inference/receipts/release-7e8f301c/`로 보존됐다.

## 확인한 차이와 실행 결과

기존 승인 receipt는 `b96e72897a27c3a6a0eee4db7c04d55efba10bbd373efe0a83f56221d8a2a847`, 복구 서버는 `7e8f301cdbe9511d4e6b108a3b8bc8ae7330b59a59b7d3dfcb69296c66bb4f0a`다. boot_id를 제외한 receipt 항목의 차이는 `runtime.tokenizers 0.23.2 → 0.23.3` 하나다. 모델·base revision·18 shard hash·adapter weight/config·native asset hash·generation policy는 동일하다.

실행 중인 GPU 프로세스의 실제 Python에서 설치 metadata를 읽어 tokenizers 0.23.3, Transformers 5.18.0.dev0, Torch 2.8.0+cu128, PEFT 0.21.0을 확인했다. 토크나이저/템플릿 파일 8개의 실제 SHA256도 receipt와 대조했다.

원출력을 수리하지 않고 현재 RunPod API에 기존 공개 합성 사례만 순서대로 3건 생성했다.

| 사례 | 실제 결과 | 판정 |
|---|---|---|
| 입력 근거 부족 | REQUEST_EVIDENCE | strict Validator 통과 |
| 한정된 입력 근거 존재 | NO_ACTION_REQUIRED | strict Validator 통과 |
| 다른 형상의 근거를 전용 | CHALLENGE | strict Validator 통과 |

세 사례의 input token 수·prompt token ID hash·rendered hash는 이전 승인 사례와 동일하다. EOS 종료·token reservation 384·4096 전체 예산·request/boot/model receipt·raw output SHA256도 검사했다. 3건을 각각 한 번 제출했고 생성 실패·boot 변경·유실 시 재생하도록 하지 않았다. 이는 제한된 연결/출력 계약 검증이며 공학 정확도·제품 적합성 전체 검증이 아니다.

## 승인 후 수행할 범위

1. `packages/contracts/model_profiles/rc3.json`의 `model_receipt_id` 하나를 위 새 receipt로 변경한다. 모델·어댑터·contract·최대 토큰·generation 설정은 보존한다.
2. 후보 receipt와 원출력·검증 결과·사용자 승인 근거를 별도 새 release 기록으로 보존한다. 이전 승인 receipt는 삭제하거나 덮어쓰지 않는다.
3. 프로젝트의 로컬 API/worker 이미지를 빌드·재생성한다. 실행 중 검토가 있으면 적용을 중단한다. DB volume·자료·사람 결정과 원격 GPU 프로세스는 유지한다.
4. 실제 인증 `/version`의 exact receipt 일치, 앱의 READY 표시와 LIVE 시연 버튼 활성화를 확인한다. 이전/알 수 없는 receipt 차단 회귀를 유지한다.

영향: 이후 새 LIVE 생성은 검증한 `tokenizers 0.23.3` runtime에서 허용된다. 현재 영수증 비교는 그대로 엄격하며, 임의 runtime을 허용하는 예외를 만들지 않는다. 원격 패키지 설치·모델 재학습·adapter 교체·RunPod 설정/비용 변경은 이 계획에 포함하지 않는다.

실행 근거: `var/run-records/runtime-alignment-20261009/CONFORMANCE_RECEIPT.json`, 세 원출력 JSON, `remote_inspection.json`, `baseline_profile.json`. 승인 전 업무 DB 쓰기는 없고 generation만 공개 합성 3건이다.
