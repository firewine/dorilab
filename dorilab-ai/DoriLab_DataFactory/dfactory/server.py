from __future__ import annotations
import json
import secrets
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
from .core import Store,public_case

PAGE=Path(__file__).with_name('review.html')

def make_handler(store: Store, token: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,payload,kind='application/json; charset=utf-8'):
            raw=payload.encode() if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(raw)
        def check_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}
        def do_GET(self):
            if not self.check_host():self.send(403,{'error':'Local host only'});return
            path=urlsplit(self.path).path
            try:
                if path=='/':self.send(200,PAGE.read_text(encoding='utf-8').replace('__TOKEN__',token),'text/html; charset=utf-8')
                elif path=='/api/cases':self.send(200,store.list_cases())
                elif path.startswith('/api/case/'):
                    cid=unquote(path.removeprefix('/api/case/'));self.send(200,public_case(store.get(cid)))
                elif path.startswith('/api/pair/'):
                    pid=unquote(path.removeprefix('/api/pair/'))
                    self.send(200,[public_case(store.get(r['case_id'])) for r in store.list_cases() if r['pair_id']==pid])
                else:self.send(404,{'error':'Not found'})
            except KeyError:self.send(404,{'error':'Unknown case'})
        def do_POST(self):
            if not self.check_host() or self.headers.get('X-DoriLab-Token')!=token:
                self.send(403,{'error':'Invalid local request token'});return
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://localhost:{port}',f'http://127.0.0.1:{port}'}:
                self.send(403,{'error':'Origin mismatch'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=262144:raise ValueError('Invalid body length')
                body=json.loads(self.rfile.read(length));path=urlsplit(self.path).path
                if path.startswith('/api/reference/'):
                    cid=unquote(path.removeprefix('/api/reference/'));store.record(cid,'REFERENCE_OPENED',body)
                    self.send(200,store.get(cid)['reference_draft'])
                elif path.startswith('/api/review/'):
                    cid=unquote(path.removeprefix('/api/review/'));self.send(200,store.record(cid,'REVIEW',body))
                else:self.send(404,{'error':'Not found'})
            except (ValueError,KeyError,TypeError) as e:self.send(400,{'error':str(e)})
        def log_message(self,fmt,*args):pass
    return Handler

def serve(store:Store,port:int=8790):
    if not 1024<=port<=65535:raise ValueError('Port must be 1024..65535')
    token=secrets.token_urlsafe(32);server=ThreadingHTTPServer(('127.0.0.1',port),make_handler(store,token,port))
    print(f'Review Desk: http://localhost:{port}',flush=True)
    print('Local prototype. CTRL+C to stop. No model/API calls or training are performed.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
