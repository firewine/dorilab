# DoriLab

프로젝트 기억, Qwen 검색 제어기와 RC3 검토를 연결하는 단일 GPU 추론 프로젝트입니다.

## 문서

- [아키텍처와 개발 예정 논문 데이터 플라이휠](docs/specifications/ARCHITECTURE_KO.md)
- [입출력 명세](docs/specifications/IO_SPEC_KO.md)
- [개발 명세](docs/specifications/DEVELOPMENT_SPEC_KO.md)
- [공개 저장소 구성](repository/UPLOAD_REPORT_KO.md)
- [추론 API 계약](inference/API_CONTRACT.md)
- [Mac 연결 절차](inference/MAC_CONNECTION_HANDOFF.md)

## 구성과 실행 전제

`project_memory/`는 프로젝트 기억과 검색 제어기, `inference/`는 HTTP API와 모델 runtime, `docs/`는 개발 명세를 담습니다. 기존 실험 코드와 고정 검증 자산은 원래 경로를 유지합니다. 논문 데이터 플라이휠의 구현 상태는 **개발 예정**입니다.

운영 경로는 `/workspace/dorilab`이며 GPU Python은 `/root/venvs/dorilab-tournament/bin/python`입니다. Qwen base는 `/root/models/qwen38-27b`, RC3 adapter는 `/workspace/dorilab/models/qwen38-27b/current/adapter`에 별도 준비해야 합니다. 자산 식별자와 SHA256은 개발 명세를 따릅니다.

RunPod 실행에는 GPU 환경, base, adapter, 서비스 token과 부팅 hook 설정이 필요합니다. bootstrap은 기존 workspace adapter를 검증하며 adapter 공급과 token 관리는 운영자가 담당합니다. 상세 시작 절차는 개발 명세와 추론 API 계약을 따릅니다.

## 공개 파일 관리

최상위 `.gitignore`는 검토한 파일 경로를 허용하는 방식입니다. 새 파일을 공개할 때는 해당 경로를 규칙에 추가하고 변경 목록을 확인합니다. 가상환경, 설치 패키지, 캐시, 모델 가중치, Codex 상태, 프로젝트 기억과 실행 로그는 운영 저장소에서 관리합니다.

공개 패키지 manifest에는 파일별 크기와 SHA256을 기록합니다. tokenizer와 processor 자산의 출처 및 라이선스는 [third-party 안내](repository/THIRD_PARTY_NOTICES.md)를 따릅니다.
