"""Capture immutable MVP audit snapshots after stopping only the smoke server."""
import datetime,hashlib,importlib.metadata as md,json,platform,socket,sqlite3,sys
from pathlib import Path
import torch,transformers
BASE=Path(__file__).resolve().parent
ROOT=Path('/workspace/dorilab')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def save(name,obj):
 with (BASE/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
registry=json.loads((BASE/'INTERNAL_MVP_CANDIDATE.json').read_text())
runtime=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),hostname=socket.gethostname(),sys_executable=sys.executable,sys_prefix=sys.prefix,
 python=platform.python_version(),transformers_file=transformers.__file__,torch_cuda=torch.version.cuda,cuda_available=torch.cuda.is_available(),
 gpu=torch.cuda.get_device_name(0),gpu_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
 package_versions={k:md.version(k) for k in ['torch','transformers','peft','accelerate']},
 transformers_direct_url=json.loads(md.distribution('transformers').read_text('direct_url.json')),
 registry_sha256=sha(BASE/'INTERNAL_MVP_CANDIDATE.json'),system_sha256=sha(registry['system_path']),generation=registry['generation'],
 tokenizer_template_assets={p:sha(p) for p in registry['processor_asset_sha256']},training_runtime_record=registry['runtime_record'])
assert runtime['sys_executable']==registry['runtime_python']
assert runtime['python']=='3.12.3' and runtime['torch_cuda']=='12.8' and runtime['cuda_available']
assert all(v==registry['runtime'][k] for k,v in runtime['package_versions'].items())
assert runtime['transformers_direct_url']==registry['runtime']['transformers_direct_url']
assert runtime['tokenizer_template_assets']==registry['processor_asset_sha256']
save('MVP_RUNTIME.json',runtime)
before=json.loads((BASE/'PRESERVATION_BEFORE.json').read_text())
mismatches=[p for p,h in before.items() if sha(p)!=h]
assert not mismatches,mismatches
assert sha(registry['adapter_weights'])==registry['adapter_sha256']
save('PRESERVATION_AFTER.json',dict(status='PASS',checked_prior_sealed_files=len(before),mismatches=mismatches,
 before_manifest_sha256=sha(BASE/'PRESERVATION_BEFORE.json'),adapter_sha256=registry['adapter_sha256'],new_training_steps=0,
 original_training_optimizer_steps=104,dev_labels_changed=False,pod_lock_touched=False,stop_touched=False,
 verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
source=BASE.parent/'mvp_rc3_smoke_work_01/factory.sqlite3'
db=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
runs=[dict(json.loads(r['payload']),content_hash=r['content_hash']) for r in db.execute('SELECT * FROM mvp_runs ORDER BY rowid')]
events=[dict(r,payload=json.loads(r['payload'])) for r in db.execute('SELECT * FROM mvp_events ORDER BY event_id')]
assert sum(r['model_called'] for r in runs)==3
assert len(runs)==8 and len(events)==12
assert all(e['payload'].get('automated_smoke') is True for e in events if e['kind']=='INTERNAL_DRAFT_REVIEW')
assert all(r['training_eligible'] is False for r in runs)
save('SMOKE_STORE_EXPORT.json',dict(source=str(source),scope='AUTOMATED_INTEGRATION_ONLY',runs=runs,events=events,human_review_performed=False))
snapshot=BASE/'SMOKE_STORE_SNAPSHOT.sqlite3'
assert not snapshot.exists()
copy=sqlite3.connect(snapshot);db.backup(copy);copy.close();db.close()
app=ROOT/'dorilab-ai/DoriLab_DataFactory'
paths=[p for p in (app/'rc3_mvp').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
reused=[app/'dfactory/core.py',app/'dfactory/server.py',app/'dfactory/review.html']
save('IMPLEMENTATION_MANIFEST.json',dict(application={str(p):sha(p) for p in sorted(paths)},
 reused_existing_sources={str(p):sha(p) for p in reused},candidate_registry_sha256=sha(BASE/'INTERNAL_MVP_CANDIDATE.json'),
 sealed_rc3_renderer=registry['sealed_tokenization_module'],sealed_rc3_renderer_sha256=sha(registry['sealed_tokenization_module']),
 application_entrypoint='rc3_mvp.server',scope='LOCAL_INTERNAL_REVIEW_ONLY'))
print(json.dumps(dict(runtime='PASS',prior_files_preserved=len(before),model_generations=3,runs=len(runs),events=len(events))))
