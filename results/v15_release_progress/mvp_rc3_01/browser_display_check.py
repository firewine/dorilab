"""Read existing runs and exercise input rejections; zero model generations."""
import datetime,json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=Path(__file__).resolve().parent
OUT=BASE/'display_check_01'
URL='http://127.0.0.1:8791'
def save(name,value):
 with (OUT/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
 OUT.mkdir(exist_ok=False)
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL);page.wait_for_function("document.querySelectorAll('#scenarios button').length===3")
  record=json.loads((BASE/'smoke_attempt02/SMOKE_LIVE_MODEL_RUN_3_SAVED.json').read_text())
  page.evaluate('(r)=>show(r)',record)
  # Render the already-recorded evidence without appending another review or model call.
  item=record['presented_evidence_snapshot'][0]
  page.evaluate("(v)=>document.getElementById('evidence').replaceChildren(el('h3',v.id),el('p',v.provided_content.text))",item)
  page.locator('#result').scroll_into_view_if_needed()
  page.screenshot(path=str(OUT/'desktop_review.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844})
  assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Mobile overflow'
  page.screenshot(path=str(OUT/'mobile_review.png'),full_page=True)
  page.set_viewport_size({'width':1440,'height':1100})
  plan=json.loads((BASE/'SMOKE_SCENARIOS.json').read_text())['scenarios'][0]['packet']
  text=json.dumps(plan,ensure_ascii=False,indent=2)
  page.locator('#reviewed').check()
  page.locator('#upload').set_input_files({'name':'reviewed_packet.json','mimeType':'application/json','buffer':text.encode()})
  assert page.locator('#packet').input_value()==text
  assert not page.locator('#reviewed').is_checked()
  results.append({'check':'JSON_UPLOAD_EXACT_TEXT_AND_ATTESTATION_RESET','status':'PASS'})
  for label,packet_text,expected in [
   ('DUPLICATE_JSON','{"case_id":"first","case_id":"second"}','DUPLICATE_JSON_KEY'),
   ('INPUT_LENGTH',json.dumps({**plan,'packet':{**plan['packet'],'review_question':'길이 검증 '*2500}},ensure_ascii=False),'INPUT_LENGTH_EXCEEDED_NO_TRUNCATION')]:
   page.locator('#packet').fill(packet_text);page.locator('#mode').select_option('REPLAY');page.locator('#reviewed').check()
   with page.expect_response(lambda r:r.url==URL+'/api/run' and r.request.method=='POST') as response:page.locator('#run').click()
   run=response.value.json();save(label+'_RUN.json',run)
   assert response.value.status==200 and not run['model_called'] and run['model_output'] is None
   assert expected in ' '.join(run['validator']['errors'])
   page.wait_for_function('(s)=>document.getElementById("validation").textContent.includes(s)',arg=expected)
   assert page.locator('#packet').input_value()==packet_text
   page.locator('#result').scroll_into_view_if_needed();page.screenshot(path=str(OUT/(label+'.png')),full_page=True)
   results.append({'check':label,'status':'PASS','run_id':run['run_id'],'model_called':False})
  assert not errors,errors
  browser.close()
 save('DISPLAY_CHECK.json',dict(status='PASS',additional_model_generations=0,results=results,page_errors=errors,mobile_overflow=False,
  font='fonts-noto-cjk 1:20230817+repack1-3 extracted under /tmp only',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
if __name__=='__main__':main()
