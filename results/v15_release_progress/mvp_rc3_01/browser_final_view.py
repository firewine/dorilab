"""Verify saved LIVE/REPLAY display labels after the history hint fix. No POST."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parent
OUT=BASE/'final_visual_01'
OUT.mkdir(exist_ok=False)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1100})
 page.goto('http://127.0.0.1:8791');page.wait_for_function("document.querySelectorAll('#scenarios button').length===3")
 for mode in ['REPLAY','LIVE_MODEL_RUN']:
  row=json.loads((BASE/f'smoke_attempt02/SMOKE_{mode}_3_SAVED.json').read_text())
  page.evaluate('(r)=>show(r)',row)
  assert mode in page.locator('#modehint').inner_text()
  assert mode in page.locator('#badges').inner_text()
 item=row['presented_evidence_snapshot'][0]
 page.evaluate("(v)=>document.getElementById('evidence').replaceChildren(el('h3',v.id),el('p',v.provided_content.text))",item)
 page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
 page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
 browser.close()
with (OUT/'RESULT.json').open('x') as f:json.dump(dict(status='PASS',mode_hint_matches_saved_run=True,additional_model_generations=0,new_review_events=0),f,indent=2)
