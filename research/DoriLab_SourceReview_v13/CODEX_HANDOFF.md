# Codex 인수인계: Qwen 27B 근거 검토 개선

## 결정

사용자는 새 출처의 검토 자료를 만들고 앞서 제안한 개선 순서로 진행하기로 했다. 기존 두 모델 동시 LoRA 계획보다 Qwen 27B의 단일 specialist 경로를 우선한다. Gemma 26B는 독립 검토와 후속 후보로 보존한다. 기존 다섯 baseline은 다시 실행하지 않는다.

이번 인계에서 실제 완료한 범위는 공개 출처 조사, 본문 기반 근거 요약, 새 합성 사례와 기대정답 후보, CPU 도구 및 검토 양식 작성이다. RunPod 파일 변경, 새 모델 추론, 학습, 독립 전문가 검토는 수행하지 않았다.

## 기존 현황: 사용자 보고

| 모델 | Action /84 | reference exact /64 | strict /84 | 진단 오수용 |
|---|---:|---:|---:|---:|
| Qwen 9B | 77 | 64 | 60 | 1 |
| Gemma 12B | 19 | 0 | 16 | 1 |
| Mistral 24B | 19 | 0 | 17 | 1 |
| Gemma 26B-A4B | 19 | 0 | 18 | 0 |
| Qwen 27B | 82 | 60 | 69 | 1 |

Gemma/Mistral의 공식 점수에는 64건의 코드 블록 형식 실패가 포함된다. 진단 오수용은 내부 JSON을 별도로 읽은 결과다. 공식 점수와 진단을 합치지 않는다. Qwen27은 Action 오류2, 근거 오류4, reason 오류11이 보고됐다.

기존 Qwen2B LoRA strict75/84, Gemma E4B LoRA strict73/84는 개발 적응 결과다. 현재 84건은 학습 source 중복과 개발 피드백 노출이 있으므로 새 출처 일반화 근거로 사용하지 않는다. 본 패키지의 원문 목록도 전체 서버 corpus와 대조한 뒤 분리를 확정해야 한다.

## 현재 서버 경로: 접속 후 확인

- 프로젝트 `/workspace/dorilab/dorilab-ai`, `/workspace/dorilab/dorilab-gemma4-e4b`
- baseline `/workspace/dorilab/tournament/baseline_v1`
- 사례 분석 `/workspace/dorilab/tournament/baseline_v1/analysis_20260923`가 보고됐으나 실제 위치는 서버 검색으로 확인
- 기존 연구 문서 `/workspace/dorilab/tournament/research/LORA_TEACHING_AND_MULTI_MODEL_2026-09-23.md`
- 이전 학습자료 `/workspace/dorilab/dorilab-ai/DoriLab_SourceCurriculum_v02/data/reason_coverage_v12/repeat246.jsonl`
- 해당 246행 SHA256 `fc94a57e1f01999b366a4ae1b9af16ec0db64e8c0fdf87df9f71bc47b039ad0d`
- 환경 `/workspace/dorilab/env.sh`, venv `/root/venvs/dorilab-tournament`
- base cache `/root/hf-cache`, 결과와 adapter는 `/workspace`

보고된 GPU는 RTX PRO 6000 Blackwell 약95 GiB, Python3.12.3, torch2.8.0+cu128, transformers5.18.0.dev0, PEFT0.21.0이다. 실제 환경과 모델 lock을 읽고 확인한다. 서버를 새로 만들거나 전체 pip upgrade하지 않는다.

## 첫 작업: CPU로 완결

1. 기존420건과 old scorer, dataset, 모델 lock의 hash/상태를 읽고 보존 목록을 만든다. 완료 모델 추론을 반복하지 않는다.
2. 이 패키지 `packtool.py validate`와 unit tests를 실행한다. PASS는 구조/계산 범위다.
3. source_manifest_v02와 모든 export/manifests, RAG index, 기존 검토 기록을 읽고 새 source의 DOI, 보고서 ID, 제목 동의어와 program overlap을 감사한다. 다른 mission 이름만으로 독립성을 선언하지 않는다. TRAIN/DEV/RESERVED의 전체 같은-source 파생자료는 한 split으로 유지한다.
4. 원문을 공식 URL에서 확보해 파일 SHA256, source title/date, 절/페이지와 짧은 paraphrase를 확인한다. NASA PDF의 표/그림 검증 실패와 MDPI 직접 접근 제한은 source manifest에 이미 명시했다. 문제가 생긴 출처를 다른 논문으로 조용히 대체하지 않는다.
5. 원문과 합성 가정 및 정책을 분리해 기대정답을 검토한다. 검토자는 가능한 한 모델 출력/정답 초안을 보기 전에 자기 판단을 먼저 기록한다. 모호한 reason과 복수 타당한 답은 추론 전에 새 label version으로 확정하거나 quarantine한다.
6. 실제 사람이 검토하지 않은 것을 `human_review_performed=true`로 바꾸지 않는다. user가 연구 진행을 승인했다는 사실을 개별 공학 정답의 승인으로 대신하지 않는다.

## 원문 다운로드 지원

TRAIN/DEV만 먼저 취급한다. source manifest의 `download_url`이 있으면 그 PDF를 받는다. 없으면 DOI와 출판사 HTML/PDF를 확보한다. 원문 파일을 `verified_sources`에 둔다. hash는 확보한 바이트로 계산한다. 권리/본문/분리 검토를 `reviews/source_review.json`에 기록한다.

자동 fetch가 HTML 오류 페이지를 PDF로 저장하지 않도록 content type과 `%PDF-`를 확인한다. 429/403은 제한된 재시도 후 보고하며 모델 승인 상태나 다른 출처로 덮지 않는다. 원문을 받지 못해도 짧은 packet 후보를 CPU 검토할 수 있지만 학습용 source release는 대기 상태를 유지한다.

원문 다운로드 명령은 다음과 같다. 이 명령은 공식 원문만 요청하며 모델 가중치를 받지 않는다. 성공한 파일도 미검토 상태로 기록한다.

```bash
python3 fetch_sources.py --ids SR13-TIRS SR13-NEA SR13-RHOBC \
  --out /workspace/dorilab/research/verified_sources_v13
```

publisher 원문은 같은 명령에서 DEV source ID를 명시하거나 공식 페이지를 브라우저로 열어 확보한다. 자동 다운로드가 제한되면 우회 인증이나 다른 논문으로 대체하지 않고 접근 상태를 기록한다.

## 새 v13 계약

`packet`에 `review_target`을 명시했다. `PROPOSED_DISPOSITION`과 `INPUT_READINESS`를 구분한다. data의 `gold_candidate.jsonl`에는 정답과 짧은 근거 관계가 있으며 입력에는 없다. input 조립은 동일 source에 배정된 모든 fact를 사용한다. gold의 필요한 source ref만 넣는 방식은 금지한다.

v13은 기존 `dcurr`/Gemma scorer 스키마를 대체하지 않는다. 별도 adapter가 필요하다. 신규 실행기는 먼저 공개 입력만 읽어 raw 결과를 저장하고, 별도 평가 프로세스가 gold와 결합한다. 동일 프로세스가 모든 파일을 읽을 수 있으면 논리적 분리와 OS 권한 분리의 차이를 기록한다.

## GPU 실험 순서

E0 CPU replay -> E1 Qwen27 direct vs short-ledger DEV 비교 -> 경로/데이터 freeze -> E2 검토된 TRAIN Qwen27 LoRA 한 번 -> 기존84/DEV 회귀 -> E3 평가자 RESERVED 비교.

E1의 새 baseline은 새 prompt/packet 성능이므로 기존84 baseline 재실행과 구분한다. 동일모델 learning effect는 같은 새 입력과 같은 추론 경로의 학습 전/후로 계산한다. 모든 기법을 한 번에 바꾸고 학습 효과라고 부르지 않는다.

TRAIN은 새48건이며 related family12개다. 기존246을 무조건 붙이는 대신 고유 상태/반복 여부와 supervised token 배분을 확인한다. 기존 contract150 + 고유 physics20 + 새48 =218행은 한 가지 계획 예시다. 실제 승인 export를 읽어 정확한 구성과 hash를 정한다. 정답 근거가 빠진 임의예제를 사용하지 않는다.

초기 hyperparameter는 r16/alpha32/dropout0.05/lr5e-5/epochs2/seed42를 출발점으로 둔다. 모델구조 target 검사와 gradient/mask/reload smoke를 먼저 통과시킨다. max length2048을 넘어가면 입력을 몰래 자르지 않는다. 사례별 실제 native tokenization을 기록하고 비용 영향과 별도 버전을 정한 뒤 budget을 바꾼다. logits 메모리 절약이 label shift나 EOS supervision을 바꾸지 않았는지도 확인한다.

전체 base model이나 router/vision 모듈이 뜻하지 않게 학습되면 중단한다. BF16과 NF4를 섞어 capacity 효과를 주장하지 않는다. 실제 GPU 상태, duration, peak allocated 및 전체메모리를 기록한다.

## 승인과 중단

사용자는 이 개선 방향과 자료 제작을 승인했다. 이 인계는 기존 데이터를 변경하거나 새 인프라를 만드는 권한을 부여하지 않는다. 현재 단계에서 원문/중복 감사, CPU 검사와 입력 준비를 진행한다. source와 label release가 준비되면 Qwen27의 계획과 예상 자원 범위를 보고하고 한 번의 고정 실험을 진행한다. Gemma 학습, DPO/RL, sweep, 새 GPU/볼륨, 모델/패키지 변경과 위험한 삭제는 별도 확인한다.

실패 run과 로그는 보존한다. 새 출력 폴더와 시간표시 로그를 사용하고 `set -o pipefail`로 Python 실패가 tee 뒤에 숨지 않도록 한다. 백그라운드 실행은 실제 tmux/작업 ID를 남긴다. 기존 실행 중 세션을 죽이거나 Pod를 stop하지 않는다.

## 제품 원칙

KASA/ECSS/NASA profile, Scope Gate, Governed Blackboard, numerical tools와 Human Review를 유지한다. 논문, 프로젝트 채택 기준과 실측의 권위는 별도 필드다. 모델의 정상 판단은 승인이나 실제 시험 실행으로 자동 전파되지 않는다.

제품 문서의 UI lifecycle과 AI 실행계약에 서로 다른 단계 수가 나오면 원문 정의를 확인한다. 이번 모델 데이터 패키지 때문에 기존15단계 rail/14단계 AI 실행계약 등을 임의 통합하거나 수정하지 않는다.

## 최종 인수 산출물

`SOURCE_AUDIT.json`, `LABEL_REVIEW_STATUS.json`, `TRAIN_BUILD_MANIFEST.json`, `TOKEN_PREFLIGHT.json`, `MODEL_TARGET_AUDIT.json`, `EXPERIMENT_LOCK.json`, source/family별 gain/loss, 위험-처리율 보고서, 모델/adapter lock, 사용자용 `NEXT_DECISION_KO.md`를 새 실험 폴더에 남긴다. 만들어지지 않은 파일은 예시 경로로 표시한다.

성공 기준은 strict 점수 상승 하나가 아니라 판단 대상 구분, source/observation 근거 연결, 오수용과 과잉 개입, 새로운 출처에서의 회귀 여부를 함께 확인하는 것이다. 제한된 24건 reserve와3source만으로 일반적인 안전률을 보장하지 않는다.
