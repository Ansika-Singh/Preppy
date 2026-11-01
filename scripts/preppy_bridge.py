"""
Preppy Local RPC Bridge Server for Web Browser Demo.
Listens on 127.0.0.1:5174 and proxies RPC requests to learn.api.handle_learn_rpc.
"""

import http.server
import json
import os
import sys
from pathlib import Path

# Ensure common/python is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "common" / "python"))

from learn.api import handle_learn_rpc


class PreppyRPCHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/api/health"):
            data = b'{"status": "ok", "app": "Preppy"}'
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ("/api/learn", "/rpc"):
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(post_body) if post_body else {}
                action = data.get("action", "")
                params = data.get("params", {})
                res = handle_learn_rpc(action, params)
                res_bytes = json.dumps(res).encode("utf-8")

                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_bytes)))
                self.end_headers()
                self.wfile.write(res_bytes)
            except Exception as e:
                err_bytes = json.dumps({"success": False, "error": str(e)}).encode("utf-8")
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Mute stdout access logs to keep terminal clean
        pass


def run_bridge(port: int = 5174):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), PreppyRPCHandler)
    print(f"Preppy Python RPC Bridge running on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_bridge()
