import http.client
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server import handler_for, permitted


class GatewayTests(unittest.TestCase):
    def test_route_allowlist(self):
        self.assertTrue(permitted("POST", "/v1/generations"))
        self.assertTrue(permitted("GET", "/v1/generations/synthetic-123"))
        for method, path in [("POST", "/version"), ("GET", "/admin"),
                             ("GET", "/version?token=x"), ("GET", "/v1/generations/../admin")]:
            self.assertFalse(permitted(method, path))

    def test_authentication_and_exact_forwarding(self):
        calls = []
        raw = b'{"raw_text":"native <|im_end|>","status":"completed"}'

        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path, self.headers.get("Authorization")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *_):
                pass

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        gateway = ThreadingHTTPServer(("127.0.0.1", 0), handler_for("test-token", upstream.server_port))
        for server in (upstream, gateway):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            client = http.client.HTTPConnection("127.0.0.1", gateway.server_port)
            client.request("GET", "/version")
            result = client.getresponse()
            self.assertEqual(result.status, 401)
            result.read()
            self.assertEqual(calls, [])
            client.request("GET", "/admin", headers={"Authorization": "Bearer test-token"})
            result = client.getresponse()
            self.assertEqual(result.status, 404)
            result.read()
            self.assertEqual(calls, [])
            client.request("GET", "/v1/generations/synthetic-123", headers={"Authorization": "Bearer test-token"})
            result = client.getresponse()
            self.assertEqual(result.status, 200)
            self.assertEqual(result.read(), raw)
            self.assertEqual(calls, [("/v1/generations/synthetic-123", "Bearer test-token")])
            client.close()
        finally:
            gateway.shutdown()
            upstream.shutdown()
            gateway.server_close()
            upstream.server_close()


if __name__ == "__main__":
    unittest.main()
