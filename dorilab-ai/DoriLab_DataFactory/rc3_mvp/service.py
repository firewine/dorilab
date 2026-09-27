import json,threading,time,uuid
from pathlib import Path
from dfactory.core import Store,digest,stamp
from .contracts import check_packet,evidence_index,parse_json,validate_output
from .model import file_sha,load_registry,RC3Model

class ReviewStore(Store):
 """Reuse the existing local SQLite connection; separate tables and work directory."""
 def __init__(self,work):
  super().__init__(Path(work))
  with self.connect() as db:db.executescript('''CREATE TABLE IF NOT EXISTS mvp_runs(id TEXT PRIMARY KEY,content_hash TEXT NOT NULL,payload TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS mvp_events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT UNIQUE NOT NULL,run_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);''')
 def add_run(self,run):
  h=digest(run)
  with self.connect() as db:db.execute('INSERT INTO mvp_runs VALUES(?,?,?)',(run['run_id'],h,json.dumps(run,ensure_ascii=False)))
  return dict(run,content_hash=h)
 def get_run(self,rid):
  with self.connect() as db:r=db.execute('SELECT * FROM mvp_runs WHERE id=?',(rid,)).fetchone()
  if r is None:raise KeyError(rid)
  return dict(json.loads(r['payload']),content_hash=r['content_hash'])
 def list_runs(self):
  with self.connect() as db:rs=db.execute('SELECT payload FROM mvp_runs ORDER BY rowid DESC').fetchall()
  return [{k:r[k] for k in ['run_id','mode','created_at','execution_status','packet_sha256']} for row in rs for r in [json.loads(row[0])]]
 def event(self,rid,kind,body):
  run=self.get_run(rid)
  if body.get('content_hash')!=run['content_hash']:raise ValueError('STALE_RUN_HASH')
  request=body.get('request_id')
  if not isinstance(request,str) or not request.strip():raise ValueError('REQUEST_ID_REQUIRED')
  encoded=json.dumps(body,ensure_ascii=False,sort_keys=True)
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT * FROM mvp_events WHERE request_id=?',(request,)).fetchone()
   if old:
    if old['payload']!=encoded or old['kind']!=kind or old['run_id']!=rid:raise ValueError('REQUEST_ID_CONFLICT')
    return {'saved':True,'duplicate':True,'event_id':old['event_id']}
   cur=db.execute('INSERT INTO mvp_events(request_id,run_id,kind,payload,created_at) VALUES(?,?,?,?,?)',(request,rid,kind,encoded,stamp()))
   return {'saved':True,'duplicate':False,'event_id':cur.lastrowid}
 def events(self,rid):
  with self.connect() as db:rs=db.execute('SELECT * FROM mvp_events WHERE run_id=? ORDER BY event_id',(rid,)).fetchall()
  return [dict(r,payload=json.loads(r['payload'])) for r in rs]

class ReviewService:
 def __init__(self,registry_path,work,engine=None,enable_live=False):
  self.registry_path=Path(registry_path);self.r=load_registry(self.registry_path);self.registry_hash=file_sha(self.registry_path)
  self.system=Path(self.r['system_path']).read_text();self.reasons=parse_json(self.system.split('Reason definitions:\n',1)[1])
  self.store=ReviewStore(work);self.engine=engine or RC3Model(self.r);self.enable_live=enable_live;self.lock=threading.Lock()
  root=self.registry_path.parent;self.scenarios=json.loads((root/'SMOKE_SCENARIOS.json').read_text())['scenarios']
  self.replay={r['id']:r for r in map(json.loads,Path(self.r['replay_raw_path']).read_text().splitlines())}
  self.replay_inputs={r['id']:r for r in map(json.loads,Path(self.r['evaluation_inputs_path']).read_text().splitlines()) if r['contract_route']=='v15_rc1' and r['cohort']=='DEV'}
 def metadata(self):return dict(candidate_id=self.r['candidate_id'],status=self.r['status'],model=self.r['model'],revision=self.r['revision'],adapter_sha256=self.r['adapter_sha256'],live_enabled=self.enable_live,loaded=self.engine.model is not None,
  scenarios=[{'id':r['id'],'label':r['label'],'packet':r['packet']} for r in self.scenarios],tool_execution=False,automatic_feedback_training=False)
 def run(self,body):
  if not self.lock.acquire(blocking=False):raise ValueError('MODEL_BUSY: 현재 검토 호출이 끝난 뒤 실행하세요.')
  try:return self._run(body)
  finally:self.lock.release()
 def _run(self,body):
  started=time.monotonic();mode=body.get('mode');packet=body.get('packet');packet_text=body.get('packet_text');parse_errors=[]
  if packet_text is not None:
   if not isinstance(packet_text,str):parse_errors.append('PACKET_TEXT_STRING_REQUIRED');packet=None
   else:
    try:packet=parse_json(packet_text)
    except ValueError as e:packet=None;parse_errors.append('INVALID_PACKET_JSON: '+str(e))
  if mode not in {'REPLAY','LIVE_MODEL_RUN'}:raise ValueError('EXPLICIT_RUN_MODE_REQUIRED')
  r=dict(run_id=str(uuid.uuid4()),mode=mode,created_at=stamp(),input_packet=packet,packet_sha256=digest(packet),registry_path=str(self.registry_path),registry_sha256=self.registry_hash,
    candidate=dict(candidate_id=self.r['candidate_id'],model=self.r['model'],revision=self.r['revision'],adapter_directory=self.r['adapter_directory'],adapter_sha256=self.r['adapter_sha256'],runtime_python=self.r['runtime_python'],runtime_record=self.r['runtime_record'],runtime=self.r['runtime'],input_contract=self.r['input_contract'],generation=self.r['generation']),
    upload_review_attestation='USER_DECLARED_REVIEWED' if body.get('reviewed_packet') is True else 'NOT_DECLARED',
    input_packet_text=packet_text,packet_text_sha256=digest(packet_text) if packet_text is not None else None,
    model_called=False,model_output=None,execution_status='INPUT_REJECTED',draft_status='REVIEW_DRAFT',training_eligible=False,engineering_approval=False,official_deployment_approval=False)
  errors=parse_errors+check_packet(packet)
  if body.get('reviewed_packet') is not True:errors.append('REVIEWED_PACKET_DECLARATION_REQUIRED')
  r['validator']=dict(status='INPUT_REJECTED',errors=errors,presented_evidence=[])
  if not errors:
   messages=[{'role':'system','content':self.system},{'role':'user','content':json.dumps(packet,ensure_ascii=False,sort_keys=True)}]
   r['input_messages']=messages;r['input_messages_sha256']=digest(messages)
   try:
    ids=self.engine.tokenize(messages);r['prompt_tokens']=len(ids);r['prompt_token_ids_sha256']=digest(ids)
    if len(ids)+self.r['generation']['max_new_tokens']>self.r['max_total_tokens']:raise ValueError('INPUT_LENGTH_EXCEEDED_NO_TRUNCATION')
    if mode=='REPLAY':
     source=self.replay_inputs.get(packet['case_id'])
     if source is None or source['messages']!=messages:raise ValueError('REPLAY_INPUT_MISMATCH: 저장된 원래 입력만 재생할 수 있습니다.')
     out=self.replay[packet['case_id']]
     if digest(ids)!=out['prompt_token_ids_sha256']:raise ValueError('REPLAY_TOKEN_MISMATCH')
     r['model_output']={k:out[k] for k in ['raw_text','text','generated_token_ids','generated_tokens','ended_with_native_terminator']}
     r['replay_provenance']=dict(path=self.r['replay_raw_path'],sha256=file_sha(self.r['replay_raw_path']),case_id=packet['case_id'],original_recorded_at=out['recorded_at'],original_latency_seconds=out['elapsed_seconds'])
    else:
     if not self.enable_live:raise ValueError('LIVE_MODEL_DISABLED: --enable-live 로 실행하세요.')
     r['model_call_attempted']=True;r['model_output']=self.engine.generate(ids);r['model_called']=True
    output=r['model_output'];r['model_output_sha256']=digest(output)
    limited=not output['ended_with_native_terminator'] and output['generated_tokens']>=self.r['generation']['max_new_tokens']
    r['validator']=validate_output(output['text'],packet,self.reasons,limited)
    r['execution_status']='DRAFT_READY' if not r['validator']['errors'] else 'OUTPUT_REJECTED'
   except Exception as e:
    r['validator']=dict(status='RUN_FAILED',errors=[type(e).__name__+': '+str(e)],presented_evidence=[])
    r['execution_status']='RUN_FAILED';r['automatic_retry']=False
  r['completed_at']=stamp();r['latency_seconds']=time.monotonic()-started
  r['presented_evidence_snapshot']=r['validator']['presented_evidence']
  return self.store.add_run(r)
 def open_evidence(self,rid,body):
  run=self.store.get_run(rid);ref=body.get('reference_id')
  item=next((x for x in run['presented_evidence_snapshot'] if x['id']==ref),None)
  if item is None:raise ValueError('REFERENCE_NOT_CITED_OR_NOT_PROVIDED')
  self.store.event(rid,'EVIDENCE_OPENED',dict(body,evidence_snapshot=item,evidence_sha256=digest(item)))
  return item
 def review(self,rid,body):
  run=self.store.get_run(rid);decision=body.get('decision')
  if decision not in {'ACCEPT','MODIFY','REJECT'}:raise ValueError('DECISION_REQUIRED')
  for k in ['reviewer','notes']:
   if not isinstance(body.get(k),str) or not body[k].strip():raise ValueError(k.upper()+'_REQUIRED')
  correction=body.get('correction_text');cv=None
  if decision=='ACCEPT' and run['validator']['status']!='CONTRACT_VALID_REVIEW_REQUIRED':raise ValueError('CANNOT_ACCEPT_INVALID_DRAFT')
  if decision=='MODIFY':
   if check_packet(run['input_packet']):raise ValueError('INPUT_INVALID: 새 packet으로 별도 실행하세요.')
   cv=validate_output(correction,run['input_packet'],self.reasons)
   if cv['errors']:raise ValueError('INVALID_CORRECTION: '+', '.join(cv['errors']))
  elif correction and correction.strip():raise ValueError('CORRECTION_REQUIRES_MODIFY_DECISION')
  return self.store.event(rid,'INTERNAL_DRAFT_REVIEW',dict(body,correction_validator=cv,
    original_output_unchanged=True,training_eligible=False,engineering_approval=False,official_deployment_approval=False,
    reviewer_identity='USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED',automated_smoke=body['reviewer'].startswith('SMOKE_TEST_')))
