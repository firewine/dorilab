"""Detached single-instance launcher. Never kills a listener or reloads a model."""
import fcntl
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SECURE = Path('/root/.config/dorilab')
os.umask(0o077)
SECURE.mkdir(parents=True, exist_ok=True, mode=0o700)
if SECURE.is_symlink() or SECURE.stat().st_uid != 0: raise SystemExit('unsafe secret directory')
SECURE.chmod(0o700)
PIDFILE = HERE / 'run/service.json'

def identity():
    try:
        info = json.loads(PIDFILE.read_text()); pid = info['pid']
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        return info if str(HERE / 'server.py').encode() in cmd else None
    except (OSError, ValueError, KeyError): return None

if '--status' in sys.argv:
    print(json.dumps({'process':identity()}, indent=2)); raise SystemExit(0)
lock = os.open(SECURE / 'inference.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    existing = identity()
    if existing: print(json.dumps({'already_running':existing})); raise SystemExit(0)
    raise SystemExit('service lock held; launch in progress or foreign owner; no second model started')
if identity(): raise SystemExit('service process exists without expected lock; inspect manually')
with socket.socket() as probe:
    try: probe.bind(('127.0.0.1',8080))
    except OSError: raise SystemExit('port 8080 occupied by another process; left untouched')
# Recover API dependencies from exact closure lock, with no transitive runtime upgrades.
subprocess.run([sys.executable, str(HERE/'restore_api.py')], check=True)
token_path = SECURE/'inference.token'
if not token_path.exists():
    candidates = [Path('/root/.dorilab/inference.token'),Path('/root/dorilab_inference.token')]
    existing = next((p for p in candidates if p.is_file()), None)
    token = existing.read_text().strip() if existing else secrets.token_urlsafe(48)
    fd = os.open(token_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,'w') as f: f.write(token+'\n')
info = token_path.lstat()
if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
    raise SystemExit('token must be root-owned regular file mode 600')
if len(token_path.read_text().strip()) < 32: raise SystemExit('existing token too short')
run = HERE/'run'; run.mkdir(exist_ok=True)
logpath = run / ('server-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.log')
env = os.environ.copy()
env.update(PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
           TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false', CUDA_VISIBLE_DEVICES='0')
with logpath.open('ab') as log:
    child = subprocess.Popen([sys.executable,str(HERE/'server.py')], stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT, cwd=HERE, env=env,
        start_new_session=True, close_fds=True, pass_fds=(lock,))
info = dict(pid=child.pid, log=str(logpath), listen='127.0.0.1:8080', started_at=time.time())
tmp = PIDFILE.with_suffix('.tmp'); tmp.write_text(json.dumps(info,indent=2)+'\n'); tmp.replace(PIDFILE)
print(json.dumps(info))
