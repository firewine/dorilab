# DoriLab Data Factory v0.1 — 구현 설계서와 검토 중심 프로토타입

**기존 학습 프로젝트를 교체하는 패키지가 아닙니다.** 논문→사례→검토→학습의 전체 설계와, 가장 먼저 고칠 검토 UI·기존 후보 import·Crossref 검색의 작은 실행본을 제공합니다.

## 파일

- `docs/IMPLEMENTATION_KO.md`: 전체 파이프라인, 데이터 계약, 검토 UI, API·LangGraph 구조, 학습 연결, 10작업일 계획.
- `dfactory/`: 별도 설치가 필요 없는 Python 표준 라이브러리 프로토타입.
- `schemas/`: 설명용 새 계약 제안. 기존 action schema를 자동 변경하지 않습니다.
- `prompts/`: 교사 사실 추출·사례 생성·별도 검토 프롬프트 초안.
- `config/`: 6개 영역 검색식과 후속 파이프라인 설정 예시.
- `examples/`: 사용자 J7 화면을 재구성한 UI 시연용 2개 사례. 학습 승인 제외.
- `reports/`: 실제 로컬 테스트 기록.

## 1. WSL 실행

ZIP을 `~/dorilab-ai`에 복사한 다음 **WSL 터미널**에서 다음을 실행합니다. 기존 GPU 환경을 변경하지 않으며 패키지 설치가 필요 없습니다.

```bash
cd ~/dorilab-ai
source .venv/bin/activate
python -m zipfile -e DoriLab_DataFactory_v01.zip .
cd DoriLab_DataFactory_v01
python -m unittest discover -s tests -v
python -m dfactory demo --work work_demo
python -m dfactory serve --work work_demo --port 8790
```

Windows 브라우저에서 `http://localhost:8790`을 엽니다. 종료는 Ctrl+C입니다.

화면은 질문·제안·관측 조건을 먼저 표시합니다. 자신의 판정을 선택하고 기준 초안을 열어 비교합니다. 실제 모델이 이유를 출력하지 않았다면 ‘이유 미출력’으로 표시합니다. 기준 초안 설명은 별도입니다. 시연 데이터를 원문 검토가 끝난 학습 정답으로 승인할 수는 없으며, 보류·수정요청 기록은 저장할 수 있습니다.

서버는 127.0.0.1에만 바인딩합니다. Mac 등 다른 장비에서 공유하는 배포·인증은 이 프로토타입 범위가 아닙니다. 필요 시 후속 SSH tunnel/인증 배포를 구성합니다.

## 2. 기존 SourceCurriculum_v02 후보 40개 가져오기

시연 서버를 종료한 뒤 다음을 실행합니다.

```bash
python -m dfactory import-current \
  --root ../DoriLab_SourceCurriculum_v02 \
  --work work_current

python -m dfactory audit --work work_current

python -m dfactory serve --work work_current --port 8790
```

원래 JSONL·CSV·adapter·v08 결과는 바뀌지 않습니다. `work_current/factory.sqlite3`에 복사하여 표시합니다. 기존 한국어 rationale은 ‘기준 초안’에서 보여주고, 없는 verdict/issue/next_step은 ‘미작성’으로 둡니다. 없는 모델 설명이나 실행결과를 보충하지 않습니다.

`v08 REVIEW.html`의 IDs와 실제 모델 로그는 이 import 대상이 아닙니다. 해당 파일의 schema를 확인한 후 별도 어댑터로 연결해야 합니다.

## 3. 검토 기록·모델 입력 내보내기

```bash
python -m dfactory export-reviews \
  --work work_current --out exports/reviews_001.jsonl

python -m dfactory export-model-inputs \
  --work work_current --out exports/inputs_001.jsonl
```

기존 파일이 있으면 새 파일명을 사용합니다. 첫 파일은 검토 이벤트이며 SFT 파일이 아닙니다. 두 번째 파일에는 정답·해설·A/B marker·모델 답변이 포함되지 않습니다. 검토결과를 dcurr.review/prepare로 반영하는 migration은 설계서의 후속 구현 항목입니다.

## 4. Crossref에서 실제 출처 후보 검색

인터넷 연결이 필요합니다. 본문이나 권리 승인 없이 메타데이터 후보만 저장합니다.

```bash
python -m dfactory discover \
  --domain THERMAL \
  --query 'spacecraft thermal balance model correlation sensor' \
  --rows 10 \
  --out work_discovery/thermal_001.jsonl
```

반복 수집에는 `--mailto`에 본인 연락용 이메일을 넣을 수 있습니다. 적합성·권리·동일 캠페인 확인 후 원문 취득 단계로 이동합니다. 6개 영역의 검색어는 `config/source_queries.json`에 있습니다.

NASA collector, PDF parser, 교사 API 호출, 자동 학습·평가는 이번 실행본에서 제공하지 않습니다. 기존 dcurr 코드와 연결하는 구체적 순서·입출력·검증은 구현 설계서에 있습니다. 명령 이름만 있고 수행하지 않는 ingest/train stub은 넣지 않았습니다.

## 5. 데이터 보존

동일 사례를 다시 import하면 중복을 만들지 않습니다. ID는 같고 내용이 다르면 원본을 덮어쓰지 않고 새 revision을 요구합니다. 검토 기록은 case hash와 reviewer·판단 이유·열람 여부를 포함합니다. 단일 사용자 개발용 로컬 서버이며 조직용 인증·권한 시스템이 아닙니다.

## 다음 개발 순서

검토 화면의 한국어 issue/reason/next_step을 사례 생성물에 포함 → 기존 원문 5개 자동 취득/파싱 → 교사 3단계 처리 → 검토 큐 → 승인 데이터 build → 기존 train/eval을 GPU 큐에 연결합니다. 자세한 작업 항목은 `docs/IMPLEMENTATION_KO.md`를 참조합니다.

## 제작 환경 확인

CPU 단위시험 18개와 기존 후보 40개 import를 확인했습니다. 브라우저 DOM·기준 초안 분리·검토 저장은 Chromium에서 로컬 HTTP bridge로 검사했습니다(제작 환경에서 브라우저의 직접 URL 접근이 제한됨). Crossref 실제 요청은 제작 환경 DNS 문제로 완료되지 않았으므로 외부 수집은 사용자 WSL에서 확인할 항목입니다. 교사 API·PDF 파싱·GPU 학습은 이번 실행본에서 수행하지 않습니다. 자세한 범위는 `reports/BUILD_STATUS.json`에 있습니다.
