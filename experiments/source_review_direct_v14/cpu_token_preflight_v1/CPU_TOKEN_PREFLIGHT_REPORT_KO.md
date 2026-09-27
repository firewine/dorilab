CPU 실제 token 검사는 8건 모두 통과했다. 최대 입력1628 + 응답384 = 2012 token으로 2048 한도 내다. GPU 생성은 실행하지 않았다. 현재 Pod의 기존 Qwen27 가중치 경로가 없고 확인한 다른 캐시 경로에서도 발견되지 않아, 가중치 다운로드 금지 지시에 따라 생성 전 중단했다. 미확인 경로까지 가중치가 전혀 없다고 단정하지는 않는다.

처음 요청은 macOS CPU였지만 연결된 실행 환경이 Linux임을 알리고 사용자로부터 “현재 환경에서 진행 승인”을 받았다. 실제 OS는 `Linux-6.17.0-19-generic-x86_64-with-glibc2.39`이다. macOS에서 검사했다고 표시하지 않는다.

| case_id | 입력 token | 입력+384 | 2048 한도 |
|---|---:|---:|---|
| CASE-8261f9621f | 1609 | 1993 | PASS |
| CASE-ec0f24fd6c | 1628 | 2012 | PASS |
| CASE-f49f3d339e | 1598 | 1982 | PASS |
| CASE-18d7b891b1 | 1534 | 1918 | PASS |
| CASE-5bf8af5346 | 1535 | 1919 | PASS |
| CASE-d48966c293 | 1628 | 2012 | PASS |
| CASE-b40f92306b | 1514 | 1898 | PASS |
| CASE-a18319c1d2 | 1515 | 1899 | PASS |

모델은 Qwen/Qwen3.8-27B, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, Transformers 5.18.0.dev0 / commit `002e1edf5b5198488297f401dd853056b6521d02`를 사용했다. commit은 설치 metadata의 vcs_info와 대조했다. 별도 `/tmp/sr14_cpu_env`에 CPU 전용 torch2.8.0+cpu / torchvision0.23.0+cpu를 설치했다. CUDA stack이나 모델 가중치를 다운로드하지 않았다. `/tmp` 환경은 Pod 중지 후 유지된다고 보증하지 않으므로 설치 로그와 freeze를 /workspace에 보존했다.

명시적 허용목록은 config.json, tokenizer_config.json, tokenizer.json, vocab.json, merges.txt, chat_template.jinja, preprocessor_config.json, video_preprocessor_config.json의 8개이다. 모두 정확한 revision URL에서 가져와 기존 MODEL_CACHE_RESTORE의 size와 SHA256을 대조했다. main/다른 revision에서 보충하지 않았다. [허용목록](ASSET_ALLOWLIST.json), [다운로드 검증](audit/ASSET_FETCH.json)에 기록했다.

원래 runner의 AutoProcessor.from_pretrained(local_files_only=True, trust_remote_code=False), apply_chat_template(tokenize=False, add_generation_prompt=True, enable_thinking=False), tokenizer(add_special_tokens=False, truncation=False) 경로를 분리해 그대로 실행했다. processor는 Qwen3VLProcessor, tokenizer는 Qwen2Tokenizer이다. 코드 AST로 기존 렌더링 호출과 동일함을 검사했다.

새 [actual_model_inputs.jsonl](runs/linux_cpu_01/actual_model_inputs.jsonl)에 case_id, messages hash, 렌더링 원문과 hash, 입력 token ID 전체와 hash, token 수, 예산 포함 수, 한도 여부, tokenizer/template 파일별 hash를 기록했다. [TOKEN_PREFLIGHT.json](runs/linux_cpu_01/TOKEN_PREFLIGHT.json)에 환경·조건·길이·출처를 기록했다. 이들은 **NEW_DIRECT_V14_CPU_PREFLIGHT_NOT_HISTORICAL_V13_INPUT_IDS**이며, 과거 보존되지 않은 v13 token ID의 원본이 아니다.

CPU 원본 산출물 SHA256 검증은 통과했다. 새 준비 코드 검사8개도 통과했다. 이전 준비 단계의 검사31개·원본34개와 혼합해 모델 성능 지표로 표시하지 않는다. 원래 v13 패키지·결과와 이전 direct_v14 준비 파일도 변경하지 않았다.

현재 Pod는 조회 당시 RUNNING 상태였고 GPU는 RTX PRO 6000 Blackwell Server Edition, memory.used=0 MiB였으며 compute process는 없었다. 이 작업에서 Pod START를 호출하지 않았다. 환경 변수의 현재 Pod ID만 사용했고 과거 ID를 하드코딩하지 않았다. 모델 snapshot을 찾지 못했으므로 모델 로드·generate·출력 보정·gold 결합을 실행하지 않았다. 새 GPU 실행의 완료 사례는 0개이며, 실패한 추론을 완료로 기록하지 않았다. 상태는 CPU_PASS_GPU_NOT_RUN_MISSING_LOCAL_WEIGHTS이다.

기존 가중치 경로를 요청한 상태이며 가중치 다운로드나 대체 revision 사용은 하지 않는다. 조회한 CLI는 `pod` top-level 명령을 지원하지 않았으며 도움말로 `runpodctl stop pod` 지원을 확인했다. 기존 finish_and_stop.sh의 legacy STOP 절차와 같다. 종료 직전에 다른 실행 작업 부재를 다시 검사하고 STOP 결과를 [audit](audit/)에 남긴다. STOP 요청/확인 상태는 stop 관련 파일이 권위 있는 기록이며 이 보고서에 미리 성공으로 기록하지 않는다.

Mac 접속 정보가 없어 Mac 회수는 미수행이다. 전체 산출물은 `/workspace/dorilab/experiments/source_review_direct_v14/cpu_token_preflight_v1`에 보존한다. Linux CPU 사용 승인과 Mac 회수 성공은 서로 다른 사실이다.

후속 실행기는 CPU/GPU 실제 렌더링·token ID·input hash·tokenizer hash·commit이 모두 동일할 때만 모델을 로드한다. 원래 GPU runner의 생성 부분4439자는 그대로 보존했다. 실패·부분 출력·마지막 완료 사례·재개 조건을 별도 control 폴더에 남기고 자동 재시도하지 않는다. 추가 비교 도구는 reason 평가 불가를 의미 오답으로 바꾸지 않으며 field error와 schema/Action/reference/strict를 별도 기록한다. [후속 명령](NEXT_GPU_COMMANDS.md)은 준비만 했고 실행하지 않았다.

새 raw 출력이 없으므로 출력 안내 변경의 관측 효과는 **아직 미측정**이다. reason_code를 reason으로 교정하지 않았고 기존 공식 점수를 변경하지 않았다. 정답은 SOURCE_GROUNDED_AI_CANDIDATE, human_review_performed=false, training_eligible=false를 유지한다. DEV8은 이미 관측한 한 출처·두 관련 family의 진단 집합이며 독립 일반화 평가나 학습 데이터가 아니다. 추가 학습·추론은 자동 시작하지 않는다.
