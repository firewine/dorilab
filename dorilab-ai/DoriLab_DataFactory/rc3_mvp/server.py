import argparse,json,secrets
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,unquote
from dfactory.server import make_handler
from .service import ReviewService
from .contracts import parse_json

def handler(service,token,port):
 # Reuse the existing local Host restriction, response security headers and logger.
 Base=make_handler(service.store,token,port)
 class Handler(Base):
  def do_GET(self):
   if not self.check_host():self.send(403,{'error':'Local host only'});return
   path=urlsplit(self.path).path
   try:
    if path=='/':self.send(200,Path(__file__).with_name('index.html').read_text().replace('__TOKEN__',token),'text/html; charset=utf-8')
    elif path=='/api/meta':self.send(200,service.metadata())
    elif path=='/api/runs':self.send(200,service.store.list_runs())
    elif path.startswith('/api/run/'):
     rid=unquote(path.removeprefix('/api/run/'));self.send(200,dict(service.store.get_run(rid),events=service.store.events(rid)))
    else:self.send(404,{'error':'Not found'})
   except KeyError:self.send(404,{'error':'Unknown run'})
  def do_POST(self):
   if not self.check_host() or self.headers.get('X-DoriLab-Token')!=token:self.send(403,{'error':'Invalid local request token'});return
   origin=self.headers.get('Origin')
   if origin and origin not in {f'http://localhost:{port}',f'http://127.0.0.1:{port}'}:self.send(403,{'error':'Origin mismatch'});return
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=262144:raise ValueError('REQUEST_BODY_LENGTH_EXCEEDED')
    body=parse_json(self.rfile.read(length).decode('utf-8'))
    if not isinstance(body,dict):raise ValueError('REQUEST_OBJECT_REQUIRED')
    path=urlsplit(self.path).path
    if path=='/api/run':result=service.run(body)
    elif path.startswith('/api/evidence/'):result=service.open_evidence(unquote(path.removeprefix('/api/evidence/')),body)
    elif path.startswith('/api/review/'):result=service.review(unquote(path.removeprefix('/api/review/')),body)
    else:self.send(404,{'error':'Not found'});return
    self.send(200,result)
   except KeyError:self.send(404,{'error':'Unknown run'})
   except (ValueError,TypeError,UnicodeError) as e:self.send(400,{'error':str(e)})
  def end_headers(self):
   self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
   super().end_headers()
 return Handler
def main():
 p=argparse.ArgumentParser();p.add_argument('--registry',required=True,type=Path);p.add_argument('--work',required=True,type=Path);p.add_argument('--port',type=int,default=8791);p.add_argument('--enable-live',action='store_true');a=p.parse_args()
 if not 1024<=a.port<=65535:raise ValueError('PORT_RANGE')
 service=ReviewService(a.registry,a.work,enable_live=a.enable_live);token=secrets.token_urlsafe(32)
 server=ThreadingHTTPServer(('127.0.0.1',a.port),handler(service,token,a.port))
 print(f'RC3 INTERNAL_MVP_CANDIDATE http://127.0.0.1:{a.port} live_enabled={a.enable_live}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
