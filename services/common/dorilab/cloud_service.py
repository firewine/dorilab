"""Supervise gateway, private original API, and existing worker on one CPU host."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .cloud_transport import validate_cloud_mode


def main():
    required = ("DORILAB_DB_CONNECTION_FILE","DORILAB_SESSION_SECRET_FILE",
                "DORILAB_SITES_TOKEN_FILE","DORILAB_SITES_IDENTITIES_FILE")
    if any(not os.getenv(name) for name in required):
        raise RuntimeError("cloud service secret files are required")
    if any(not Path(os.environ[name]).is_file() or not Path(os.environ[name]).read_text().strip() for name in required):
        raise RuntimeError("cloud service secret files are unavailable")
    if os.getenv("DORILAB_ARTIFACT_BACKEND") != "postgres":
        raise RuntimeError("cloud hosting requires durable artifacts")
    validate_cloud_mode()
    port = int(os.getenv("PORT","8000"))
    if not 1 <= port <= 65535 or port == 8001:
        raise RuntimeError("invalid public gateway port")
    os.environ["DORILAB_API_UPSTREAM"] = "http://127.0.0.1:8001"
    os.environ.setdefault("DORILAB_WORKER_WAKE_FILE","/tmp/dorilab-cloud/worker.wake")
    commands = [
        [sys.executable,"-m","uvicorn","dorilab.api:app","--host","127.0.0.1","--port","8001","--workers","1","--no-access-log"],
        [sys.executable,"-m","dorilab.cloud_worker"],
        [sys.executable,"-m","uvicorn","dorilab.sites_gateway:app","--host","0.0.0.0","--port",str(port),"--workers","1","--no-access-log"],
    ]
    processes = []
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        for command in commands:
            processes.append(subprocess.Popen(command))
        while not stopping:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("cloud child process exited; restart whole service")
            time.sleep(0.25)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
