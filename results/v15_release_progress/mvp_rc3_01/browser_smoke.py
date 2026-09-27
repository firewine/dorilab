"""Exactly three REPLAY + three LIVE integration flows, never a new benchmark."""
import datetime,hashlib,json,os,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).resolve().parent;URL='http://127.0.0.1:8791'
def save(name,obj):
 with (OUT/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 plan=json.loads((OUT/'SMOKE_SCENARIOS.json').read_text());scenarios=plan['scenarios'];results=[];errors=[]
 freeze=dict(started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scenario_sha256=sha(OUT/'SMOKE_SCENARIOS.json'),
   script_sha256=sha(__file__),scope='INTEGRATION_SMOKE_ONLY_NOT_INDEPENDENT_PERFORMANCE_EVALUATION',
   modes=['REPLAY','LIVE_MODEL_RUN'],live_generation_limit=3,expected_actions=[r['expected_action'] for r in scenarios],
   review_decisions=['ACCEPT','MODIFY','REJECT'],automated_modify_reason='SUPPORTING_EVIDENCE_MISSING',
   human_review_performed=False,feedback_training=False)
 save('SMOKE_EXECUTION_SCOPE.json',freeze)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL);page.wait_for_function("document.querySelectorAll('#scenarios button').length===3")
  for mode in freeze['modes']:
   for i,scenario in enumerate(scenarios):
    page.locator('#scenarios button').nth(i).click();page.locator('#reviewed').check();page.locator('#mode').select_option(mode)
    with page.expect_response(lambda r:r.url==URL+'/api/run' and r.request.method=='POST',timeout=600000) as response:
     page.locator('#run').click()
    http=response.value;assert http.status==200,http.text();run=http.json()
    save(f"SMOKE_{mode}_{i+1}_RUN.json",run) # Raw and exact packet persisted before assertions.
    assert run['mode']==mode and run['draft_status']=='REVIEW_DRAFT'
    assert run['execution_status']=='DRAFT_READY',run['validator']
    assert run['model_called']==(mode=='LIVE_MODEL_RUN')
    assert run['validator']['parsed']['action']==scenario['expected_action'],'Frozen flow action mismatch; do not adapt expectation'
    assert run['input_packet']==scenario['packet']
    assert run['input_messages_sha256']==scenario['input_messages_sha256'],'Native input drift'
    assert run['validator']['semantic_reference_sufficiency']=='NOT_AUTOMATICALLY_VERIFIED'
    page.wait_for_function("document.querySelector('#status').textContent.includes('DRAFT_READY')")
    assert mode in page.locator('#badges').inner_text()
    assert page.locator('#raw').inner_text()==run['model_output']['raw_text']
    evidence=run['presented_evidence_snapshot'];assert evidence
    assert [x['id'] for x in evidence]==run['validator']['cited_reference_ids']
    page.locator('#citations button').first.click();page.locator('#evidence p').wait_for()
    assert page.locator('#evidence p').inner_text()==evidence[0]['provided_content']['text']
    decision=freeze['review_decisions'][i];page.locator('#decision').select_option(decision)
    if decision=='MODIFY':
     correction=dict(run['validator']['parsed']);correction['reason']=freeze['automated_modify_reason']
     page.locator('#correction').fill(json.dumps(correction,ensure_ascii=False,indent=2))
    page.locator('#reviewer').fill('SMOKE_TEST_AUTOMATION_NOT_HUMAN')
    page.locator('#notes').fill('Automated integration test of '+decision+'. Not a human label review; not engineering approval; do not train on this feedback.')
    with page.expect_response(lambda r:r.url==URL+'/api/review/'+run['run_id'] and r.request.method=='POST') as response:
     page.locator('#save').click()
    assert response.value.status==200,response.value.text()
    page.wait_for_function("document.querySelector('#saved').textContent.includes('저장 완료')")
    persisted=page.request.get(URL+'/api/run/'+run['run_id']).json();reviews=[e for e in persisted['events'] if e['kind']=='INTERNAL_DRAFT_REVIEW'];opened=[e for e in persisted['events'] if e['kind']=='EVIDENCE_OPENED']
    assert len(reviews)==1 and len(opened)==1
    event=reviews[0]['payload'];assert event['decision']==decision and event['automated_smoke'] and not event['training_eligible'] and not event['engineering_approval']
    assert persisted['model_output']==run['model_output'],'Original output changed after review'
    if decision=='MODIFY':assert event['correction_validator']['parsed']['reason']==freeze['automated_modify_reason']
    save(f"SMOKE_{mode}_{i+1}_SAVED.json",persisted)
    page.screenshot(path=str(OUT/f'screen_{mode}_{i+1}.png'),full_page=True)
    results.append(dict(mode=mode,scenario_id=scenario['id'],expected_action=scenario['expected_action'],run_id=run['run_id'],
       decision=decision,raw_output_preserved=True,cited_evidence_exact=True,review_saved=True,packet_sha256=run['packet_sha256'],
       model_output_sha256=run['model_output_sha256'],latency_seconds=run['latency_seconds'],status='PASS'))
    save(f'SMOKE_PROGRESS_{len(results):02d}.json',results)
    print(mode,scenario['id'],'FLOW_PASS',decision,'seconds',round(run['latency_seconds'],2),flush=True)
  assert not errors,errors
  # HTTP guard checks do not request model generation.
  assert page.request.post(URL+'/api/run',data='{}',headers={'Content-Type':'application/json'}).status==403
  assert page.request.get(URL+'/api/meta',headers={'Host':'untrusted.example'}).status==403
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'screen_mobile.png'),full_page=True)
  browser.close()
 save('SMOKE_RESULTS.json',dict(status='PASS',scope=freeze['scope'],results=results,live_generations=3,replays=3,
       expected_values_unchanged=True,new_model_performance_scores=False,page_errors=errors,http_guards='PASS',human_review_performed=False,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
if __name__=='__main__':
 try:main()
 except Exception as e:
  save('SMOKE_FAILURE.json',dict(error=repr(e),traceback=traceback.format_exc(),automatic_regeneration=False));raise
