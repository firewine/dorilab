# 100문항 세트 자동 분리와 개별 검토

2026-10-10. 이번 단계는 파일 하나를 문항별 미검토 목록으로 저장하고 사람이 수정·승인·기각하는 기능이다. 실제 LoRA 학습, 승인 사례의 데이터 버전 고정·내보내기, 원 논문 검증은 활성화하지 않았다.

## 사용 순서

1. `http://localhost:18000` → **개발·모델 관리 → 학습 사례 작성·검토**.
2. 100Q 통합검토 Markdown 하나를 선택하고 **자동 분리 · 검토 목록에 저장**.
3. 현재 로컬 MVP에서는 상단 **시연 역할 → 검토 책임자** 또는 **승인권자**로 전환한다. 엔지니어는 등록·조회만 가능하다.
4. 문항을 선택해 질문·모델 입력·정답 초안·오답·오답 이유·출처·기존 메모를 확인한다. 입력·정답은 수정할 수 있다.
5. 검토 사유와 확인 체크를 입력하고 **승인하고 다음 문항**, 또는 사유를 입력하고 **기각하고 다음 문항**을 누른다. 새로고침 후에도 원본과 결정 기록이 유지된다.

전달된 `DoriLab_100Q_통합검토_핸드오프_v1.0.md`를 실제 로컬 DORI-01 프로젝트에 등록했다. **전체 100 / 미검토 100 / 승인 0 / 기각 0 / 학습용 87 / 평가 전용 13**이다. 실제 자료를 대신 승인하지 않았다. 원본 SHA256은 `f051fd39146850ba8dcab8cdb9b9e58bfcf9f323ac467c064e2d79dca101e756`이다.

## 분리와 승인 범위

파서는 전용 Q001~Q100 원 입력·답안 섹션에서 번호·유형·TRAIN/EVALUATION·출처 묶음·출처 ID·판본·위치·질문·원 모델 입력·정답/오답/오답 이유·채점항목·검토 메모를 읽는다. 이후 수정 제안 섹션을 별도 정답으로 중복 등록하지 않는다. 실제 파일은 30개 출처 묶음, 37개 출처 ID, 28개 문항 유형이며 분류 정보 누락·학습/평가 묶음 충돌은 없었다. 이는 파일에 기재된 분류를 추출한 결과이며 원 논문이나 묶음의 의미를 검증한 결과가 아니다.

현재는 DoriLab 100Q 핸드오프 v1 형식·UTF-8·20 MiB 이하만 지원한다. 개수·번호·필수 항목·미검토 라벨 오류 또는 다른 형식은 명시적으로 거부하고 문항을 부분 저장하지 않는다. 임의의 PDF에서 질문·정답을 생성하거나 불명확한 출처를 추정하지 않는다.

문항 결정의 범위는 `LOCAL_LABEL_REVIEW_ONLY`다. 원 논문 검증·자료 이용 승인·제품 성능 승인과 구분한다. 평가 문항은 승인하더라도 TRAIN으로 이동하지 않으며 오답을 정답으로 내보내지 않는다. 현재 모든 항목의 `training_eligible=false`다. 입력·정답 수정본은 결정 기록에 따로 저장하고 원본 payload·hash·오답은 보존한다. 결정 후 재수정은 새 파일/세트로 재검토한다.

같은 파일과 등록 메타데이터의 재업로드는 기존 세트를 반환하고 승인 기록을 초기화하지 않는다. Idempotency-Key를 별도 보존해 다른 내용의 키 재사용을 409로 거부한다. 원본 bytes·권리·판본·항목 hash 변경은 STALE이며 과거 이력을 남기고 새 승인을 차단한다. 기존 혼합 세트를 원 논문 청크로 재사용해 수동 사례의 원문 검증을 우회하지 못한다.

## 데이터 흐름과 변경 파일

브라우저 파일 선택 → 기존 Artifact 업로드 → `POST /api/v1/projects/{p}/learning/imports` → 원본 hash 검사·엄격한 분리 → PostgreSQL 세트/문항 저장 → `GET /api/v1/learning/imports/{id}` → 분류 목록/상세 → `POST /api/v1/learning/import-items/{id}/decisions` → membership·CSRF·version·현행성 검사 → 결정/AuditEvent 저장 → 다음 문항 조회.

- `learning_import.py`, `learning_imports.py`, `learning.py`: 추출·영속 등록·개별 결정과 기존 사례 API 연결.
- `migrations/016_learning_imports.sql`: 세트·문항·요청 키·결정 테이블의 추가 migration. 기존 라벨·결정·업무 데이터는 일괄 변경하지 않는다.
- `apps/web/learning-sets.js`, `development.js`, `index.html`, `styles.css`: 파일 하나 등록·분류 필터·한 문항 검토·수정·결정 이력.
- `tests/test_learning_import.py`, `test_web_assets.py`: 등록/결정 반례와 정적 파일 검사.
- `sites/dorilab/scripts/sync-local-workbench.mjs` 및 동기화된 Workbench 파일: 기존 Sites 소스에 같은 화면과 새 스크립트 포함. 공개 Site·Render·Neon 배포는 이번에 수행하지 않았다.
- `README_LOCAL_DOCKER.md`, 본 기록, `STATUS.md/json`: 사용법과 실제 범위.

## 직접 확인한 결과

| 검사 | 결과 |
|---|---|
| 전체 격리 회귀 | 252 passed, 46.96초, 기존 Starlette/anyio deprecation warning 1개 |
| 최종 반영 이미지 관련 회귀 | 50 passed, 10.24초. 세트 등록·권한·CSRF·중복 키·타 프로젝트·불완전 형식·수정본/원본 분리·평가 제외·STALE·기존 사례/화면 |
| 최종 JavaScript 문법 | Node 22 컨테이너에서 새 검토 모듈과 development.js PASS |
| 실제 파일 분리 | 네트워크 없는 컨테이너에서 100/87/13·출처 묶음 30·출처 ID 37·유형 28·분류 오류 0 |
| 격리 브라우저 | 합성 100문항 업로드 → Q001 수정/승인 → Q002 기각 → 다음 문항 이동 → 새로고침/기존 세트 열기에서 승인1·기각1 유지. 평가 필터 13개·engineer 읽기 전용 확인 |
| 사용자 로컬 앱 | 실제 파일 업로드·100문항 미검토 등록·검토자 화면의 승인/기각 버튼 확인. console error 없음. 실제 문항 승인·모델 생성·학습 없음 |
| 반영과 보존 | additive migration 후 로컬 API만 재빌드/재시작. DB volume·첨부·worker·SSH 터널 유지 |

브라우저 검사에서 engineer 화면의 숨겨진 사유 필드 접근과 등록부의 `document` 변수 shadowing 오류를 발견해 수정하고 재확인했다. 도구의 잘못된 탭/메시지 locator 조회와 read-only DOM에서 FileList 조회는 실패했지만, 실제 등록·승인·기각 결과는 각각 화면에서 확인했다.

실행 기록은 `var/run-records/learning-set-review-20261010/`의 합성 fixture·최종 pytest 로그·합성/실제 화면에 있다. 원본 업로드 bytes는 기존 `var/artifacts/`, 문항·결정은 PostgreSQL에 저장된다. macOS arm64, Docker context `desktop-linux`, Linux aarch64 컨테이너, Compose 5.5.1에서 실행했다. 호스트 Python/Node 설치, RunPod 학습 또는 모델 교체, 공개 배포·push는 수행하지 않았다.

논문의 의미적 정답·실제 이용 권리, 임의 문서 형식, 실제 통신 응답 유실/동시 브라우저 조작, 공개 Site에서의 새 API·DB migration, LoRA 실행·후보 평가·적용은 이번에 검증하지 않았다. 다음 별도 작업은 검토한 TRAIN 문항의 데이터 버전 고정·학습 레시피용 내보내기다.
