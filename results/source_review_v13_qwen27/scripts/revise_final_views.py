from pathlib import Path
import json,shutil,hashlib
root=Path(__file__).resolve().parents[1];history=root/'report_revisions';history.mkdir()
for name in ['FINAL_REPORT_KO.md','SUMMARY.json','RUN_MANIFEST.json','NEXT_DECISION_KO.md','LABEL_REVIEW_STATUS.json']:
 shutil.copy2(root/name,history/(name+'.before_score_layer_split'))
o=json.load(open(root/'RAW_OFFICIAL_SCORE.json'));d=json.load(open(root/'DIAGNOSTIC_SEMANTIC_VIEW.json'));s=json.load(open(root/'SUMMARY.json'))
s['raw_official_score']=o;s['diagnostic_semantic_view']=d
s['legacy_counts_note']='counts are untouched current scorer outputs; action_correct is computed before schema validation. See explicit two layers.'
s['conclusions']={'lora_necessity_demonstrated':False,'clearest_observed_issue':'OUTPUT_CONTRACT_FIELD_ERROR','semantic_reason_error_inferred_from_reason_code':False,'raw_official_output_repair_applied':False,'tirs_rationale_status':'HUMAN_REVIEW_PENDING','mdpi_status':'SOURCE_UNAVAILABLE','source_program_audit_complete':False,'audit_scope':{'text':716,'manifest_registry':55,'sqlite':2,'rag_index':'UNCONFIRMED'},'reserved_test_accessed':False}
(root/'SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
m=json.load(open(root/'RUN_MANIFEST.json'));m.update(raw_official_summary='RAW_OFFICIAL_SCORE.json',raw_official_case_results='RAW_OFFICIAL_CASE_RESULTS.jsonl',diagnostic_semantic_summary='DIAGNOSTIC_SEMANTIC_VIEW.json',diagnostic_semantic_case_results='DIAGNOSTIC_SEMANTIC_CASE_RESULTS.jsonl',diagnostic_is_official_score=False,source_program_audit_complete=False,lora_necessity_demonstrated=False)
(root/'RUN_MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
l=json.load(open(root/'LABEL_REVIEW_STATUS.json'));l['tirs_rationale_status']='HUMAN_REVIEW_PENDING';l['independent_human_review_status']='HUMAN_REVIEW_PENDING';(root/'LABEL_REVIEW_STATUS.json').write_text(json.dumps(l,ensure_ascii=False,indent=2)+'\n')
text=(root/'FINAL_REPORT_KO.md').read_text()
a=text.index('| 진단 지표 |');b=text.index('로딩 ',a)
replacement='''### RAW OFFICIAL SCORE

현재 `packtool.evaluate_output(..., normalize=False)`의 결과를 그대로 기록했다. raw 출력 수정, fence 해제, 필드명 변경, 정답에 맞춘 보정은 하지 않았다. 이 실행 내의 official scoring track이며, 정답의 지위는 여전히 **SOURCE_GROUNDED_AI_CANDIDATE**이다. 전문가 승인 평가로 승격하지 않는다.

| 현재 scorer 지표 | 결과 | 해석 |
|---|---:|---|
| JSON valid | 8/8 | 원본 JSON 파싱 가능 |
| Schema valid | 4/8 | 네 건은 필드 계약 위반 |
| Strict | 3/8 | raw strict 결과 |
| Action | 8/8 | 현재 scorer는 schema 검사 전에 Action을 계산함. 계약 유효 처리 8건을 뜻하지 않음 |
| Reason correct | 0/4 | 적용대상 네 건 전부 schema 오류로 의미 채점에 도달하지 못함 |
| Evidence refs exact | true 3 / false 1 / 미평가 4 | schema 오류 네 건의 refs를 official exact 성공으로 포함하지 않음 |
| Parser error | 0 | 파싱 오류 없음 |
| Schema error | 4 | 모두 `unexpected answer fields` |
| Generation limit | 0/8 | 응답 token limit 미도달 |

| Case ID | JSON | Schema | Strict | Action | Reason | Evidence refs | Parser/schema error |
|---|---|---|---|---|---|---|---|
| CASE-8261f9621f | valid | valid | fail | 일치 | 비적용 | 불일치 | 없음 |
| CASE-ec0f24fd6c | valid | fail | fail | 일치 | schema 단계 미평가 | 미평가 | unexpected answer fields |
| CASE-f49f3d339e | valid | fail | fail | 일치 | schema 단계 미평가 | 미평가 | unexpected answer fields |
| CASE-18d7b891b1 | valid | fail | fail | 일치 | schema 단계 미평가 | 미평가 | unexpected answer fields |
| CASE-5bf8af5346 | valid | valid | pass | 일치 | 비적용 | 일치 | 없음 |
| CASE-d48966c293 | valid | valid | pass | 일치 | 비적용 | 일치 | 없음 |
| CASE-b40f92306b | valid | fail | fail | 일치 | schema 단계 미평가 | 미평가 | unexpected answer fields |
| CASE-a18319c1d2 | valid | valid | pass | 일치 | 비적용 | 일치 | 없음 |

`reason_code` 출력 사례는 **CASE-ec0f24fd6c, CASE-f49f3d339e, CASE-18d7b891b1, CASE-b40f92306b**이다. 이 네 건은 **OUTPUT_CONTRACT_FIELD_ERROR**로 분류하며 **SEMANTIC_REASON_ERROR로 분류하지 않는다**. `reason_code`를 `reason`으로 바꿔 공식 점수를 재계산하지 않았다. 정상 사례 CASE-8261f9621f는 후보가 요구하는 source ref를 누락했다.

원본 scorer 객체와 error 문자열은 RAW_OFFICIAL_CASE_RESULTS.jsonl, 공식 집계는 RAW_OFFICIAL_SCORE.json에 보존했다.

### DIAGNOSTIC SEMANTIC VIEW

이 층은 **official score가 아니다**. raw JSON 내부에서 `action` 값 자체가 읽히는 경우에만 Action을 비교했다. 읽을 수 있는8건 중8건이 **SOURCE_GROUNDED_AI_CANDIDATE 정답의 Action과 일치**했다. 이는 전문가 승인 정확도, 일반화 성능, 안전률 또는 계약 유효 처리율이 아니다. 네 건의 schema 실패는 그대로 남는다.

reason_code 교정, reason 의미의 사후 채점, repaired-output official 재채점은 하지 않았다. DIAGNOSTIC_SEMANTIC_VIEW.json 및 DIAGNOSTIC_SEMANTIC_CASE_RESULTS.jsonl에 Action 비교만 별도로 저장했다. 후보와의 파싱된 Action 비교에서 오수용0/4·과잉개입0/4이더라도 요청/반박 네 건이 schema 실패이므로 안전한 처리라는 결론을 낼 수 없다. 한 출처·두 관련 family만으로 일반화 또는 안전률을 추정하지 않는다. 기존84 점수와 차감해 학습 효과를 주장하지 않는다.

### 이번 관측의 결론

- **이번 DEV8에서 LoRA 필요성을 입증하지 못했다.**
- **관측된 가장 명확한 문제는 reason 필드 계약 위반이다.**
- prompt에서 정확한 JSON key 명시, schema 검증, constrained decoding, product adapter는 출력 계약을 해결할 후속 후보이다. 이를 의미 판단 학습 문제와 분리한다. 어느 후보가 효과적인지는 이번 실행에서 검증하지 않았다.
- **출력 보정은 이번 공식 결과에 적용하지 않았다.** 이후 product adapter를 실험하더라도 별도 버전·별도 결과로 평가해야 한다.
- TIRS rationale 반복 문제는 **HUMAN_REVIEW_PENDING**으로 유지한다.
- MDPI 두 source는 **SOURCE_UNAVAILABLE**로 유지한다.
- source/program 중복 감사는 확인한 **716 text, 55 manifest/registry, SQLite 2개 범위에 한정**한다. **RAG index 미확인 때문에 완료로 선언하지 않는다.**
- **EvaluatorOnly와 RESERVED_TEST에는 접근하지 않았다.**

'''
text=text[:a]+replacement+text[b:]
text=text.replace('기존 RUN_MANIFEST의 입력·gold·scorer hash 6개가 모두 일치했다.','기존 RUN_MANIFEST의 입력·gold·scorer hash 6개가 모두 일치했다. 시작 시 보존한 4,969개 파일도 최종 재검증에서 변경이 없었다.')
(root/'FINAL_REPORT_KO.md').write_text(text)
(root/'NEXT_DECISION_KO.md').write_text('''이번 DEV8은 LoRA 필요성을 입증하지 못했다. 가장 명확한 문제는 reason 필드 대신 reason_code를 출력한 OUTPUT_CONTRACT_FIELD_ERROR이다. 의미 reason 오류로 분류하지 않는다.

다음에는 정확한 출력 key를 명시하는 prompt/schema/constrained decoding/product adapter 후보를 의미 판단 학습과 분리하여 검토한다. 이번 공식 결과에는 출력 보정을 적용하지 않았다. direct/ledger 경로와 LoRA는 미선정·미실행이다.

TIRS rationale 반복은 HUMAN_REVIEW_PENDING, MDPI 두 출처는 SOURCE_UNAVAILABLE, 독립 label/권리 release는 대기다. source/program 중복 감사는 text716·manifest/registry55·SQLite2개에 한정되며 RAG index 미확인으로 완료가 아니다. RESERVED_TEST는 미접근이다.

기존 repeat246을 합치지 않았고 contract150 + 고유physics20 + 미승인TRAIN48의 계획 membership/hash만 보존했다. 학습 export와 gradient/mask/reload 검사는 승인 후 진행 대상이다. Gemma, sweep, 새 GPU/볼륨, 전체 upgrade, 삭제는 별도 확인 대상이다.
''')
print('Final report and manifests revised; original draft snapshots preserved')
