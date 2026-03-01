#!/usr/bin/env python3
"""Local OAuth callback listener for Feishu authorization code flow."""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class CallbackState:
    def __init__(self) -> None:
        self.done = False
        self.payload: dict[str, str] = {}


def build_handler(state: CallbackState, expected_path: str, expected_state: str | None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args):  # noqa: A003
            return

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != expected_path:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            query = parse_qs(parsed.query, keep_blank_values=True)
            code = query.get("code", [""])[0]
            incoming_state = query.get("state", [""])[0]
            error = query.get("error", [""])[0]
            error_desc = query.get("error_description", [""])[0]

            state.payload = {
                "path": parsed.path,
                "full_query": parsed.query,
                "code": code,
                "state": incoming_state,
                "error": error,
                "error_description": error_desc,
                "state_matched": (expected_state is None or incoming_state == expected_state),
            }
            state.done = True

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if expected_state is not None and incoming_state != expected_state:
                body = "<html><body><h3>State mismatch</h3><p>You can close this tab.</p></body></html>"
            elif error:
                body = "<html><body><h3>Authorization failed</h3><p>You can close this tab.</p></body></html>"
            else:
                body = "<html><body><h3>Authorization received</h3><p>You can close this tab.</p></body></html>"
            self.wfile.write(body.encode("utf-8"))

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listen for Feishu OAuth callback and capture authorization code.")
    parser.add_argument("--host", default="localhost", help="Listen host. Default: localhost")
    parser.add_argument("--port", type=int, default=8080, help="Listen port. Default: 8080")
    parser.add_argument("--path", default="/callback", help="Callback path. Default: /callback")
    parser.add_argument("--state", help="Optional expected OAuth state value.")
    parser.add_argument("--timeout", type=int, default=300, help="Wait timeout in seconds. Default: 300")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = CallbackState()
    handler = build_handler(state, args.path, args.state)
    server = HTTPServer((args.host, args.port), handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    start = time.time()
    try:
        while not state.done and (time.time() - start) < args.timeout:
            time.sleep(0.2)
    finally:
        server.shutdown()
        server.server_close()

    result = {
        "host": args.host,
        "port": args.port,
        "path": args.path,
        "timeout_sec": args.timeout,
        "received": state.done,
        "callback": state.payload if state.done else {},
    }
    if args.compact:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not state.done:
        return 1
    payload = state.payload
    if payload.get("error"):
        return 2
    if args.state and not payload.get("state_matched"):
        return 3
    if not payload.get("code"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
