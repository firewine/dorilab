# 평가 실행과 누수 방지

## 보존할 기존 결과

사용자가 제공한 5개 baseline의 420개 생성 결과와 기존 frozen 84건은 그대로 유지한다. 파일을 재채점하여 기존 official 점수를 대체하지 않는다. 원본 JSON strict, 코드 블록 제거 진단, 새 v13 계약을 이름과 출력 폴더로 구분한다.

현재의 우선 후보는 Qwen/Qwen3.8-27B다. 모델 ID와 전체 revision SHA는 서버의 기존 MODEL_LOCK.json에서 읽는다. 이 패키지는 서버를 조회하거나 GPU로 새 평가하지 않았다.

## 실험 분리

### E0: CPU replay

저장된 raw output을 그대로 읽고 원래 scorer 결과와 형식 어댑터 결과를 별도 출력한다. 허용 어댑터는 출력 전체가 단일 JSON 코드 블록일 때 바깥 fence만 벗기는 것부터 시작한다. JSON substring 선택, 잘린 JSON 완성, 필드 추정, reason/ref 수정과 channel 표식 임의 제거는 수행하지 않는다.

### E1: DEV에서 추론 구조 선택

같은 Qwen27 revision, BF16, native template와 직접 생성 조건을 고정한다. direct_v13과 짧은 review ledger 후 Action 생성 경로를 새 DEV 24건에서 비교한다. ledger는 모델 가설이며 validator가 의미 진실을 보증하지 않는다. ledger가 모호할 때 Human Review로 전달한다.

변경한 prompt, decoder, 최종 JSON 변환, token 수와 지연을 별도 기록한다. 전체 입력/출력 budget과 공통 조건을 적는다. 내부 검토 경로가 더 많은 토큰/호출을 썼다는 사실을 비용 비교에서 숨기지 않는다. 새 패키지로 얻은 점수를 과거 다른 prompt baseline과 단순 차감해 LoRA 효과라고 부르지 않는다.

이 단계에서 test 패키지를 읽지 않는다. prompt 탐색을 반복 확대하지 말고 두 경로의 제한된 비교 후 경로를 고정한다.

### E2: 승인된 TRAIN으로 Qwen27 LoRA 한 번

선택한 추론 경로의 baseline을 고정한 뒤 학습한다. 새 TRAIN 원문/정답 review와 기존 데이터 dedup, manifest를 확정한다. 기존 고유 physics와 contract replay의 포함량을 기록한다. 같은 모델의 baseline과 LoRA를 같은 입력/decoder/precision으로 평가한다.

r16, alpha32, dropout0.05, lr5e-5, epochs2, seed42, response-only loss는 첫 고정 비교의 출발 제안이다. 실제 architecture의 target, trainable parameter 수, nonzero finite gradient, answer+end-token mask, checkpoint reload와 메모리를 먼저 검사한다. attention/MLP/hybrid recurrent 경로 이름을 이전 E4B 구조에서 추측하지 않는다. sweep이나 새로운 quantization을 동시에 도입하지 않는다.

기존 84건과 DEV는 회귀로 사용한다. 독립 test는 선택과 prompt 수정에 사용하지 않는다.

### E3: 별도 보관한 RESERVED_TEST

사용자/평가자가 source/program 중복과 정답 검토를 끝낸 뒤, baseline/LoRA revision과 모든 실행 조건을 freeze한다. 테스트 입력만 모델 추론 프로세스에 제공한다. 모델 출력 파일 hash가 확정된 뒤 평가자가 gold를 열어 채점한다.

최소 분리: 개발 Codex 작업 폴더에는 main ZIP만 둔다. 평가자는 evaluator ZIP을 별도 환경에 두고 `render --split RESERVED_TEST`로 입력을 생성한다. 생성 프로세스에 금지할 것은 정답/해설/선정된 gold 근거이며, 추론 시 제공되는 논문 문맥 자체는 허용한다.

더 강한 분리를 원하면 평가 실행 OS 사용자/컨테이너를 분리한다. root 권한의 같은 Codex가 양쪽 파일을 볼 수 있으면 파일명이나 안내문만으로 비공개가 보장되지 않는다. 노출이 발생하면 incident를 남기고 해당 set을 DEV로 강등한다.

## 최소 지표

- Raw JSON/schema 유효성, 응답 완결성, output-limit 도달 수
- Action, evidence exact/precision/recall, 요청 항목, reason joint와 Action이 맞을 때의 reason
- gold CHALLENGE 분모의 잘못된 정상 판정, gold REQUEST의 조기 정상 판정
- gold 정상 사례의 과잉 개입, Human Review 요청률, 완결된 초안 비율
- source와 관련 가족별 성능, 두 상태가 모두 맞는 family 비율
- baseline->LoRA gain/loss, 특히 기존 정답에서 오답으로 바뀐 사례
- 입력/출력 token, 생성/로딩/전체 지연, peak allocated와 실제 GPU 사용, 실행 precision

파싱 실패는 처리 실패다. 안전한 정상 판단으로 세지 않는다. 모든 어려운 문제를 보류하는 모델도 coverage가 낮음을 함께 보고한다. 관련 가족과 source별 cluster가 있으므로 96개를 독립 Bernoulli 표본으로 취급하지 않는다. 출처가 split별 3개뿐이라 안정적인 일반화 신뢰구간이나 안전률 주장은 제한된다.

## 두 입력 경로

현재 제공 packet은 사람이 필요한 근거를 정리한 상황의 AI 저작 근사다. 이것을 raw PDF RAG 성능으로 부르지 않는다. 후속에는 같은 DEV 문제에 대해 1) 검토된 근거 packet, 2) 실제 PDF parser/retriever packet을 비교한다. 1만 맞으면 모델 용량보다 문맥 추출/검색을 먼저 본다.

## 중단 조건

old input/gold/scorer hash 변경, source/program 누수, 미검토 정답의 자동 승격, silent truncation, 잘못된 native template, base weight trainable, 비유한 gradient, 무관한 패키지 업그레이드가 발견되면 해당 실행을 멈추고 원인을 기록한다. 모델의 틀린 응답을 gold에 맞게 고치는 재시도는 없다. 결과를 본 뒤 test gold를 바꾸려면 새 버전과 오염 상태를 명시한다.
