CPU token 검사: 8/8 PASS, 최대 입력1628 + 응답384 = 2012/2048.

GPU 생성: 미실행. 고정 revision 가중치의 기존 로컬 경로가 없어 다운로드 금지 지시를 유지하며 중단했다.

STOP: 현재 환경 변수 RUNPOD_POD_ID로 runpodctl stop pod를 실행했으나 exit1, `Error: Pod is locked`로 실패했다. 삭제/TERMINATE 또는 잠금 우회는 하지 않았다. 후속 조회 상태는 audit/POD_STATUS_AFTER_FAILED_STOP.json에 있다.

잠금 해제 후 동일 STOP 재시도에 대한 사용자 승인을 요청했다. STOP 성공으로 표시하지 않는다.

Mac 회수: 연결 정보가 없어 미수행. /workspace에 CPU 산출물 및 checksum 검증 결과를 보존했다. 새 모델 raw 출력과 비교 점수는 없다.
