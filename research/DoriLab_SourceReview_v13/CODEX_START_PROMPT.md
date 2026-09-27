# Codex에 붙여 넣을 시작 프롬프트

DoriLab Qwen 27B 개선 작업을 이어간다.

먼저 `/workspace/dorilab/research/DoriLab_SourceReview_v13/README_KO.md`, `CODEX_HANDOFF.md`, `EVALUATION_PROTOCOL.md`, `ANNOTATION_POLICY.md`를 읽어라. 이미 완료한 다섯 baseline420건과 기존 frozen84건은 재실행하거나 변경하지 마라.

이번 우선순위는 Qwen27 단일 specialist다. Gemma26은 독립 검토/후속 후보로 남긴다. 모델 토론, DPO/RL, 분야별 adapter와 sweep을 동시에 도입하지 마라.

이 패키지는 TRAIN48, DEV24와 별도 평가자 RESERVED24를 출처/program 단위로 나눴다. 모두 원문 기반 AI 저작 기대정답 후보다. 독립 사람 검토, 전체 기존 source manifest 중복 감사와 PDF 화면 검증은 아직 완료되지 않았다. `human_review_performed=false`와 `training_eligible=false`를 실제 승인 없이 변경하지 마라.

첫 실행은 CPU 작업이다.

```bash
cd /workspace/dorilab/research/DoriLab_SourceReview_v13
python3 packtool.py validate
python3 -m unittest discover -s tests -v
```

현재 RunPod 프로젝트와 기존 MODEL_LOCK, 환경 freeze, 소스 manifest, 학습 export, RAG index를 읽어 이 패키지와의 출처/program 중복을 감사해라. 기존 source ID가 다르더라도 동일 논문/프로그램의 파생자료인지 확인해라. 원문은 official URL에서 확보하고 실제 bytes의 SHA256, 본문 위치, 권리와 내용 검토 상태를 기록해라. source의 `raw_file_sha256=null`에 임의 값을 채우지 마라.

검토 대상은 `PROPOSED_DISPOSITION`과 `INPUT_READINESS`로 분리했다. 정답의 relation과 expected는 모델 입력에 넣지 마라. `packtool render`는 공개 입력만 읽도록 되어 있다. 정답을 참고해 필요한 reference만 넣거나 누락된 모델 필드를 채우지 마라.

`DoriLab_SourceReview_v13_EvaluatorOnly.zip`은 구현 Codex가 열거나 검색/색인하지 마라. 사용자 또는 별도 평가자가 보관한다. 최종 조건을 고정한 후 테스트 입력만 추론에 전달하고, 출력 hash 확정 후 별도 평가자가 gold를 결합한다. 같은 root 사용자가 양쪽을 읽으면 실제 보안상 봉인이 되지 않는다는 점을 보고해라.

출처와 label release가 준비되면 새 DEV에서 Qwen27 direct와 짧은 review ledger 경로를 제한적으로 비교하고 경로를 고정한다. 같은 경로의 baseline과 검토된 TRAIN으로 학습한 LoRA를 비교해라. 과거84는 회귀용이며 새 source 일반화 수치로 사용하지 마라.

기존 repeat246에 새 데이터를 무조건 합치지 말고, 기존 고유 physics 상태와 contract replay를 구분해 새 build와 hash를 만든다. 아키텍처별 LoRA target, base freeze, gradient, response/end-token mask, native template와 checkpoint reload를 먼저 검사한다. 입력이 token limit을 넘으면 조용히 자르지 마라.

GPU/볼륨 생성, 패키지 전체 upgrade, 삭제, Gemma 추가 학습, sweep은 별도 확인을 받아라. 모든 기존 데이터, gold, 결과와 실패 로그를 보존하고 새 출력 폴더를 사용해라. `set -o pipefail`로 실패 상태를 보존해라.

첫 보고에는 현재 환경과 기존 결과의 보존 상태, CPU 검사 결과, 출처 중복/원문 검증 문제, label review 대기 항목, Qwen27 한 번의 고정 비교를 시작할 수 있는지와 필요한 결정만 정리해라. 형식 PASS를 의미 정확성이나 공학 승인으로 표현하지 마라.
