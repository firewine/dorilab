"""Rebind unchanged token measurements after guard-only changes; retain previous reports."""
from common import *
old=read(OUT/'CPU_PREFLIGHT_v2.json')
# The actual rendering/tokenization implementation and all measured inputs/assets must be identical.
guard_only={str(OUT/'common.py'),str(OUT/'train_once.py')}
for p,h in old['input_file_sha256'].items():
 if p not in guard_only:assert sha(p)==h,p
new=dict(old)
new.update(created_at_utc=now(),measurement_reuse={'prior_report':'CPU_PREFLIGHT_v2.json','prior_report_sha256':sha(OUT/'CPU_PREFLIGHT_v2.json'),'justification':'Tokenization/exporter/analysis code, native assets, membership and input/gold files unchanged. Only streaming hash helper, active report path and guarded trainer bookkeeping/config plumbing changed. Final CPU tests separately exercise guards and representative native masks.','re_render_required':False},input_file_sha256={p:sha(p) for p in old['input_file_sha256']})
put(PREFLIGHT.name,new)
status('RC3_CPU_PREFLIGHT_FINAL_BINDINGS',['native206/DEV16 측정값 유지, 최종 guard 코드 hash 연결','초기 및 v2 결과 보존'],['GPU 메모리 fit 미검증','release 승인 대기'],[PREFLIGHT.name],['단일 설정안 및 승인 묶음 작성','최종 gate 회귀 테스트'],['B03_USER_REVIEW','GPU_MEMORY_UNVERIFIED'])
