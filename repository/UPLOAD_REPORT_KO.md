# GitHub 공개 패키지 준비 기록

대상: `https://github.com/firewine/dorilab` (public). 상태: **로컬 패키지 준비**. 원격 반영 여부는 실제 push 결과와 remote commit 조회로 판정합니다.

## 공개 범위

검토한 payload는 439개 파일, 26,768,508byte (25.53MiB)입니다. Git에는 별도로 manifest, 보고서와 `.gitignore`가 추가됩니다. 기존 원격 저장소의 LICENSE와 이력을 보존합니다.

코드와 문서, runtime lock, 고정 계약, 합성 예제, native tokenizer/processor 자산, 원본 검증 receipt를 선별했습니다. tokenizer 자산 추가로 초기 코드 후보 집계보다 용량이 증가했습니다.

## 별도 운영 자산

가상환경, 설치 패키지, 캐시, 모델 가중치, Codex 상태, 프로젝트 기억, 실행 로그, 백업, 원문 PDF, 수집한 HTML과 DB dump는 workspace 또는 별도 자산 저장소에서 관리합니다. 과거 학습과 평가 재현에는 각 실행이 참조하는 원본 데이터와 release 자산을 별도로 준비해야 합니다.

## 서비스 의존성

기존 runtime은 `results/v15_release_progress/cpu_rc3/`의 원본 모듈과 `experiment_rc3_resume_01/`의 계약 입력 및 CHECKPOINT_HASHES를 사용합니다. native processor는 `experiments/source_review_direct_v14/cpu_token_preflight_v1/`의 고정 자산을 사용합니다. checkpoint 검증용 index와 shard receipt18개도 보존합니다.

base와 RC3 adapter 가중치는 별도 운영 자산입니다. 모델 경로, revision, adapter SHA256은 [개발 명세](../docs/specifications/DEVELOPMENT_SPEC_KO.md)를 따릅니다. Git clone 후 서비스 기동에는 이 자산들과 GPU runtime 준비가 필요합니다.

## 점검과 업로드

공개 전 파일 hash, 100MiB 상한, 인증정보 패턴, 제외 규칙, source preservation과 tokenizer allowlist를 점검합니다. 원격 반영은 기존 main 이력을 이어가는 일반 push로 수행합니다. 패키지별 검증 결과는 PUBLIC_EXPORT_VALIDATION.json에 기록합니다.

공개 push는 자동 승인 검토에서 보류되었습니다. 사유는 선별 파일의 구체적인 공개 범위 승인 필요입니다. 현재 원격 반영 상태는 대기입니다. 이 환경의 GitHub 인증 설정도 별도 준비가 필요합니다.
