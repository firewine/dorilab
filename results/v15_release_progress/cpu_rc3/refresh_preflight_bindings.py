"""Rebind unchanged token measurements after guard-only changes; retain previous reports."""
import ast
from common import *
old=read(OUT/'CPU_PREFLIGHT_v3.json')
# The actual rendering/tokenization implementation and all measured inputs/assets must be identical.
guard_only={str(OUT/'common.py'),str(OUT/'train_once.py'),str(OUT/'exporter.py')}
# Check the exporter functions used for token measurement are AST-identical to the measured implementation.
def functions(p):return {n.name:ast.dump(n) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)}
before=functions(OUT/'implementation_revisions/pre_source_scope_v2/exporter.py');after=functions(OUT/'exporter.py')
for name in ['require','verify_bindings','validate_record','load_candidates','inference_messages']:assert before[name]==after[name],name
for p,h in old['input_file_sha256'].items():
 if p not in guard_only:assert sha(p)==h,p
new=dict(old)
new.update(created_at_utc=now(),measurement_reuse={'prior_report':'CPU_PREFLIGHT_v3.json','prior_report_sha256':sha(OUT/'CPU_PREFLIGHT_v3.json'),'justification':'Tokenization/analysis code, native assets, membership and input/gold files unchanged. Exporter input-selection, field validation and inference functions are AST-identical to the archived measured version. Only active report/approval paths and approval-only source-role guards changed. Final tests exercise new approval gates and native masks.','re_render_required':False},input_file_sha256={p:sha(p) for p in old['input_file_sha256']})
put(PREFLIGHT.name,new)
status('RC3_CPU_PREFLIGHT_FINAL_BINDINGS',['native206/DEV16 측정값 유지, 최종 guard 코드 hash 연결','초기 및 v2 결과 보존'],['GPU 메모리 fit 미검증','release 승인 대기'],[PREFLIGHT.name],['단일 설정안 및 승인 묶음 작성','최종 gate 회귀 테스트'],['B03_USER_REVIEW','GPU_MEMORY_UNVERIFIED'])
