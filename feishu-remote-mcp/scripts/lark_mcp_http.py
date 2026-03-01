#!/usr/bin/env python3
"""Call Feishu remote MCP over HTTP JSON-RPC."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://mcp.feishu.cn/mcp"
ENV_UAT = "FEISHU_MCP_UAT"
ENV_TAT = "FEISHU_MCP_TAT"


def parse_json_object(raw: str, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must decode to a JSON object.")
    return parsed


def resolve_token(token_type: str, token: str | None) -> tuple[str, str]:
    if token:
        if token_type == "auto":
            if token.startswith("u-"):
                return token, "X-Lark-MCP-UAT"
            if token.startswith("t-"):
                return token, "X-Lark-MCP-TAT"
            raise ValueError("Cannot infer token type from --token. Pass --token-type uat|tat.")
        header = "X-Lark-MCP-UAT" if token_type == "uat" else "X-Lark-MCP-TAT"
        return token, header

    if token_type == "uat":
        value = os.environ.get(ENV_UAT)
        if value:
            return value, "X-Lark-MCP-UAT"
        raise ValueError(f"--token not provided and {ENV_UAT} is empty.")

    if token_type == "tat":
        value = os.environ.get(ENV_TAT)
        if value:
            return value, "X-Lark-MCP-TAT"
        raise ValueError(f"--token not provided and {ENV_TAT} is empty.")

    tat = os.environ.get(ENV_TAT)
    if tat:
        return tat, "X-Lark-MCP-TAT"
    uat = os.environ.get(ENV_UAT)
    if uat:
        return uat, "X-Lark-MCP-UAT"
    raise ValueError(
        "No token found. Set FEISHU_MCP_TAT or FEISHU_MCP_UAT, or pass --token with --token-type."
    )


def normalize_allowlist(raw: str) -> str:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return ",".join(values)


def build_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": args.request_id,
        "method": args.method,
    }

    if args.method == "tools/call":
        if not args.tool_name:
            raise ValueError("--tool-name is required when --method is tools/call.")
        body["params"] = {
            "name": args.tool_name,
            "arguments": parse_json_object(args.arguments, "--arguments"),
        }
        return body

    if args.params:
        body["params"] = parse_json_object(args.params, "--params")
    return body


def parse_response_body(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def is_tool_error(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    result = parsed.get("result")
    return isinstance(result, dict) and bool(result.get("isError"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feishu remote MCP HTTP JSON-RPC client.",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint URL (default: {DEFAULT_URL})")
    parser.add_argument(
        "--token-type",
        choices=("auto", "uat", "tat"),
        default="auto",
        help="Token type. Default auto: prefer FEISHU_MCP_TAT then FEISHU_MCP_UAT.",
    )
    parser.add_argument("--token", help="Token value. If omitted, read from environment.")
    parser.add_argument(
        "--allowed-tools",
        default="",
        help="Comma-separated MCP tool allowlist for X-Lark-MCP-Allowed-Tools.",
    )
    parser.add_argument("--method", required=True, help="JSON-RPC method (initialize, tools/list, tools/call).")
    parser.add_argument("--tool-name", help="Tool name for tools/call.")
    parser.add_argument(
        "--arguments",
        default="{}",
        help='Tool arguments JSON object for tools/call. Example: \'{"docID":"doccn..."}\'',
    )
    parser.add_argument("--params", help="JSON object for non-tools/call methods.")
    parser.add_argument("--request-id", type=int, default=1, help="JSON-RPC id value.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        token_value, auth_header = resolve_token(args.token_type, args.token)
        payload = build_body(args)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    headers = {
        "Content-Type": "application/json",
        auth_header: token_value,
    }
    allowlist = normalize_allowlist(args.allowed_tools)
    if allowlist:
        headers["X-Lark-MCP-Allowed-Tools"] = allowlist

    request_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(args.url, data=request_bytes, method="POST")
    for key, value in headers.items():
        request.add_header(key, value)

    status = 0
    response_raw = ""
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            status = response.status
            response_raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        print(f"[error] Network failure: {exc.reason}", file=sys.stderr)
        return 3

    parsed = parse_response_body(response_raw)
    envelope = {
        "http_status": status,
        "auth_header": auth_header,
        "request": payload,
        "response": parsed,
    }
    if args.compact:
        print(json.dumps(envelope, ensure_ascii=False))
    else:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))

    if status >= 400:
        return 1
    if is_tool_error(parsed):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
