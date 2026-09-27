# DoriLab Source Review v13

작성일: 2026-09-24. 용도: Qwen 27B 단일 specialist의 근거 검토 개선과 새 출처 평가 준비.

## 바로 시작

이 폴더를 기존 프로젝트와 별도로 `/workspace/dorilab/research/DoriLab_SourceReview_v13`에 둔다.
`CODEX_HANDOFF.md`와 `CODEX_START_PROMPT.md`부터 읽는다.

```bash
cd /workspace/dorilab/research/DoriLab_SourceReview_v13
python3 packtool.py validate
python3 -m unittest discover -s tests -v
python3 packtool.py render --split DEV --out /workspace/dorilab/tournament/source_review_v13/dev_inputs_v1.jsonl
```

위 명령은 모델을 로딩하거나 학습하지 않는다. `render`는 정답 파일을 읽지 않고 입력, 근거 registry와 공통 정책만 사용한다. 이미 존재하는 출력 파일에는 덮어쓰지 않는다.

## 패키지 구성

| 구분 | 출처 | 기본 사례 | 관련 사례 가족 | 목적 |
|---|---:|---:|---:|---|
| TRAIN | 3 | 48 | 12 | 검토 승인 후 학습 후보 |
| DEV | 3 | 24 | 6 | 추론 방식 선택과 오류 분석 |
| RESERVED_TEST | 3 | 24 | 6 | 별도 평가자 패키지에 보관 |

기본 96건은 독립 실물시험 96회가 아니다. 24개 관련 사례 가족에서 제안 대조와 입력 준비 대조를 구성한 합성 문제다. 추가로 6건의 Human Review 경계 예시가 `workflow_probes`에 있다. 이 6건은 기본 Action 평가나 SFT export에 포함하지 않는다.

핵심 파일:

- `sources/source_manifest.json`: TRAIN/DEV 논문과 검토 범위, 원문 링크, 판본 구분
- `sources/facts.json`: 짧은 근거 요약과 절/페이지 locator
- `data/train`, `data/dev`: 모델 입력, 별도 기대정답, 평가자 metadata
- `REVIEW_CARDS_KO.md`: 질문, 근거, 기대 출력과 판단 이유를 모은 검토 카드
- `packtool.py`: CPU 구조 검사, 입력 조립, 새 계약용 오프라인 채점, 검토 승인된 SFT export
- `reviews`: 비어 있는 승인 기록 양식
- `CURRICULUM_KO.md`, `EVALUATION_PROTOCOL.md`, `ANNOTATION_POLICY.md`: 제작 및 평가 기준
- `BEHAVIOR_TEST_PLAN.md`: ID/순서 변화, 근거 개입, 문맥 품질 비교

## 정답의 상태

기대정답은 `SOURCE_GROUNDED_AI_CANDIDATE`다. 논문 본문에서 확인한 원리, 새로 작성한 합성 관측과 DoriLab의 검토 정책을 결합했다. Action과 reason 코드 자체를 논문이 지정했다고 해석하지 않는다.

독립 사람 검토, 실제 장비 검증과 후보 모델의 새 추론은 수행하지 않았다. 모든 기본 사례에 `human_review_performed=false`, `training_eligible=false`가 들어 있다. 이 상태를 감추거나 승인한 것으로 바꾸지 않는다. 정책상 검토된 입력과 정답의 hash에 승인 기록을 연결한 뒤 export한다.

원문 PDF 바이트를 이 패키지에 포함하지 않았다. NASA PDF는 파싱된 본문을 확인했지만 화면 캡처 접근이 실패했고, 일부 출판사 본문은 검색 색인을 통해 확인했다. 따라서 원문 파일 hash는 `null`, 화면 검토는 미완료다. 표/그림에서 실측 숫자를 전사하지 않았다. 코드가 재계산하는 숫자는 입력에 명시한 합성값이다. Codex가 원문을 확보해 페이지와 hash를 고정해야 한다.

## 평가자 파일을 분리

`DoriLab_SourceReview_v13_EvaluatorOnly.zip`은 구현 Codex의 작업 디렉터리나 검색 색인에 넣지 않는다. 사용자 또는 별도 평가자가 보관한다. 모델, prompt, decoder와 adapter 선택이 끝난 뒤 입력만 추론 프로세스에 전달하고 출력이 봉인된 후 평가자가 정답과 결합한다.

단순히 ZIP을 분리했다고 보안상 봉인되지는 않는다. 실제 읽기 권한과 개발자 노출 기록이 필요하다. 이번 출처는 기존에 알려진 출처와 구분했으나 사용자의 전체 로컬 source manifest 대조는 아직 대기다. 공개 논문이 base model 사전학습에 없었다는 주장도 하지 않는다.

## 학습의 다음 단계

기존 420건 baseline과 frozen 84건을 보존한다. Qwen 27B의 원문 기반 판단 대상을 우선 개선한다. 새 DEV에서 direct와 짧은 검토 기록 방식의 차이를 먼저 측정하고, 정해진 방식에서 같은 모델의 학습 전/후를 비교한다. Gemma 26B는 이후 잔여 오류를 봐서 결정한다.

검토 승인 없는 SFT export는 실패하도록 만들었다. 이 CPU 도구는 기존 `dcurr.train`의 manifest를 흉내 내지 않는다. 실제 학습기 연결은 기존 코드를 읽은 Codex가 새 버전 어댑터로 구현한다.
