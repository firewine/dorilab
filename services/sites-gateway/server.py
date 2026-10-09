"""Authenticated HTTP bridge to the existing loopback inference API.

No GPU packages, model loading, token rotation, shell actions, or Pod management.
Deploy only after the user approves the separate HTTPS exposure plan.
"""
from __future__ import annotations

import argparse
import hmac
import http.client
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GET_PATHS = {"/healthz", "/readyz", "/version"}
JOB_PATH = re.compile(r"/v1/generations/[A-Za-z0-9_-]{1,128}\Z")
BODY_LIMIT = 65536


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def permitted(method: str, path: str) -> bool:
    return (method == "GET" and (path in GET_PATHS or bool(JOB_PATH.fullmatch(path)))) or (
        method == "POST" and path == "/v1/generations"
    )


def handler_for(token: str, upstream_port: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DoriLabBridge/1"

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            # No request paths, headers, input/output, or credentials in access logs.
            pass

        def respond(self, status: int, body: bytes):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.forward()

        def do_POST(self):
            self.forward()

        def forward(self):
            if not permitted(self.command, self.path):
                return self.respond(404, b'{"detail":"route unavailable"}')
            auth = self.headers.get_all("Authorization", [])
            if len(auth) != 1 or not hmac.compare_digest(auth[0], "Bearer " + token):
                return self.respond(401, b'{"detail":"authentication required"}')
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) > 1:
                return self.respond(400, b'{"detail":"unsupported framing"}')
            try:
                length = int(lengths[0]) if lengths else 0
            except ValueError:
                return self.respond(400, b'{"detail":"invalid content length"}')
            if length < 0 or length > BODY_LIMIT:
                return self.respond(413, b'{"detail":"request too large"}')
            if self.command == "GET" and length:
                return self.respond(400, b'{"detail":"GET body forbidden"}')
            if self.command == "POST" and self.headers.get_content_type() != "application/json":
                return self.respond(415, b'{"detail":"JSON required"}')
            self.connection.settimeout(15)
            upstream = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=20)
            try:
                body = self.rfile.read(length) if length else None
                if body is not None and len(body) != length:
                    return self.respond(400, b'{"detail":"incomplete body"}')
                upstream.request(self.command, self.path, body=body, headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                })
                response = upstream.getresponse()
                result = response.read(1024 * 1024 + 1)
                if len(result) > 1024 * 1024:
                    return self.respond(502, b'{"detail":"upstream response too large"}')
                # Preserve upstream JSON bytes and errors; no generated-text repair.
                self.respond(response.status, result)
            except (OSError, http.client.HTTPException):
                self.respond(503, b'{"detail":"SERVICE_NOT_DEPLOYED"}')
            finally:
                upstream.close()

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=19124)
    parser.add_argument("--upstream-port", type=int, default=8080)
    parser.add_argument("--token-file", default="/root/.config/dorilab/inference.token")
    args = parser.parse_args()
    if not (1 <= args.port <= 65535 and 1 <= args.upstream_port <= 65535):
        parser.error("invalid port")
    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if not token or any(c.isspace() for c in token):
        raise SystemExit("invalid service token file")
    server = BoundedServer(("0.0.0.0", args.port), handler_for(token, args.upstream_port))
    server.serve_forever()


if __name__ == "__main__":
    main()
