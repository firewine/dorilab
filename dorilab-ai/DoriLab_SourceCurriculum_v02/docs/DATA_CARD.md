# Dataset card — Physics candidates40 v0.2

- 목적: reference-grounded engineering review 행동 SFT의 후보와 검토 workflow.
- 현재 건수: 40 records, 20 contrastive pairs, 4 source documents, 3 domains represented.
- 기존분: Apollo TH-01 16, Wijker VB-X1 16. 원본과 expected는 불변.
- 신규분: AMSU EMI/EMC EE-02 4, OPA855 SEE EE-03 4.
- 행동: NO_ACTION_REQUIRED20, CHALLENGE12, REQUEST_EVIDENCE8.
- 모든사례 basis: SYNTHETIC_COUNTERFACTUAL. 논문 원문 원리를 이용한 가상 상태·제안이며 실제 센서 raw 데이터가 아니다.
- 사람검토: PENDING40, APPROVED0. 정답은 출처 원리와 DoriLab 검토정책을 결합한 후보다.
- 원문확인: 기존32는 이전 패키지의 본문 텍스트 검토 이력; 신규8은 해당 PDF 본문 절을 확인. 새 표/그림 수치 전사 없음.
- 공개범위: 전체40개와 정답을 패키지에 제공. 독립 숨김 평가세트로 사용하지 않음.
- Split 원칙: paper만 아니라 program/run/experiment family와 pair를 함께 묶음.
- 원문 접근: 원본PDF 미포함; downloader/공식링크 제공. 원문을 받은 후 해시와 권리 검토 기록 필요.
- 원본보존: legacy32_unmodified.jsonl은 이전 source package의 case 파일과 SHA-256 동일.
- 버전 변경: training export는 physics-review-v0.2 / physics-review-action-v0.2 사용; EEE reason3개 추가. 기존 원본 레코드의 v0.1 필드도 보존.
- 수치적 모델: 온도·응력·고장률 surrogate를 학습할 raw measurement dataset이 아님.
- 구현평가: strict JSON, schema/ref validity, action, contract pass, pair-both-pass와 timing을 구분.
- 한계: 소수문헌, 작은 source family, 합성상태, 영어 입력 중심, 실제 고객자료 미검증. 현재 candidate score를 제품의 전체 검토 성능으로 환산하지 않음.
