"""Token-file HTTP client: no token on command line or in logs. Default: version only."""
import argparse,json,os,pathlib,time,urllib.request,urllib.error
p=argparse.ArgumentParser()
p.add_argument('--base-url',default=os.getenv('DORILAB_API_URL','http://127.0.0.1:8080'))
p.add_argument('--token-file',default=os.getenv('DORILAB_TOKEN_FILE','/run/secrets/dorilab_token'))
p.add_argument('--request-file',type=pathlib.Path)
a=p.parse_args();token=pathlib.Path(a.token_file).read_text().strip()
def call(path,body=None):
 data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
 req=urllib.request.Request(a.base_url+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise SystemExit(f'HTTP {e.code}: '+e.read().decode())
v=call('/version');print(json.dumps(v,ensure_ascii=False,indent=2))
if a.request_file:
 accepted=call('/v1/generations',json.loads(a.request_file.read_text()))
 print(json.dumps(accepted));deadline=time.monotonic()+300
 while True:
  result=call('/v1/generations/'+accepted['id'])
  if result['status'] in ('completed','failed'):
   print(json.dumps(result,ensure_ascii=False,indent=2));break
  if time.monotonic()>deadline:raise SystemExit('poll timeout; do not replay blindly, retain accepted job ID')
  time.sleep(1)
