from common import *
for name in ['common.py','exporter.py','prepare_approval.py','test_release.py','refresh_preflight_bindings.py']:
 text('implementation_revisions/pre_source_scope_v2/'+name,(OUT/name).read_text())
put('SOURCE_GATE_SCOPE_REVISION.json',{'created_at_utc':now(),'reason':'A replay source is intentionally not novel. Keep original source-use gates, but require legacy split-role verification rather than falsely declaring novelty. New TRAIN source gates retain content/rights/split-novelty requirements.','prior_bundle_preserved':'APPROVAL_BUNDLE.json','prior_pending_approval_preserved':'RELEASE_APPROVAL_PENDING.json','new_bundle':'APPROVAL_BUNDLE_v2.json','targets_or_inputs_changed':False})
