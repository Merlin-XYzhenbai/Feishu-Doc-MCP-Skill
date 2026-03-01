#!/usr/bin/env python3
"""Utilities for Feishu OAuth user_access_token workflows."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

AUTH_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
REFRESH_URL = TOKEN_URL

ENV_APP_ID = "FEISHU_APP_ID"
ENV_APP_SECRET = "FEISHU_APP_SECRET"


def _print_json(data: dict[str, Any], compact: bool) -> None:
    if compact:
        print(json.dumps(data, ensure_ascii=False))
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _env_or_value(value: str | None, env_name: str, field: str) -> str:
    if value:
        return value
    env_val = os.environ.get(env_name)
    if env_val:
        return env_val
    raise ValueError(f"{field} is required. Pass argument or set {env_name}.")


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url=url, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_after(seconds: int | None) -> str | None:
    if not isinstance(seconds, int):
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"State file {path} must contain a JSON object.")
    return data


def _save_state(path: str, data: dict[str, Any]) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _mask(token: str | None) -> str:
    if not token:
        return ""
    if len(token) <= 16:
        return token[:4] + "..."
    return token[:8] + "..." + token[-8:]


def _update_state_with_oauth_tokens(
    state: dict[str, Any],
    parsed: dict[str, Any],
    client_id: str,
    client_secret: str,
    redirect_uri: str | None,
) -> dict[str, Any]:
    state["app_id"] = client_id
    state["app_secret"] = client_secret
    if redirect_uri:
        state["redirect_uri"] = redirect_uri

    if parsed.get("code") != 0:
        return state

    state["updated_at"] = _iso_now()
    scope = parsed.get("scope")
    if isinstance(scope, str):
        state["scope"] = scope

    access_token = parsed.get("access_token")
    expires_in = parsed.get("expires_in")
    if isinstance(access_token, str):
        state["uat"] = {
            "access_token": access_token,
            "expires_in": expires_in,
            "expires_at": _iso_after(expires_in if isinstance(expires_in, int) else None),
            "token_type": parsed.get("token_type"),
            "updated_at": _iso_now(),
        }

    refresh_token = parsed.get("refresh_token")
    refresh_expires_in = parsed.get("refresh_token_expires_in")
    if isinstance(refresh_token, str):
        state["refresh"] = {
            "refresh_token": refresh_token,
            "expires_in": refresh_expires_in,
            "expires_at": _iso_after(refresh_expires_in if isinstance(refresh_expires_in, int) else None),
            "updated_at": _iso_now(),
        }

    return state


def cmd_auth_url(args: argparse.Namespace) -> int:
    state = args.state or secrets.token_urlsafe(24)
    query: dict[str, str] = {
        "response_type": "code",
        "client_id": _env_or_value(args.client_id, ENV_APP_ID, "--client-id"),
        "redirect_uri": args.redirect_uri,
        "state": state,
    }
    if args.scope:
        query["scope"] = args.scope
    if args.code_challenge:
        query["code_challenge"] = args.code_challenge
        query["code_challenge_method"] = args.code_challenge_method

    url = f"{AUTH_URL}?{urllib.parse.urlencode(query)}"
    result = {
        "authorize_url": url,
        "state": state,
        "note": "Open this URL in browser to get authorization code.",
    }
    _print_json(result, args.compact)
    return 0


def cmd_exchange_code(args: argparse.Namespace) -> int:
    try:
        client_id = _env_or_value(args.client_id, ENV_APP_ID, "--client-id")
        client_secret = _env_or_value(args.client_secret, ENV_APP_SECRET, "--client-secret")
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": args.code,
    }
    if args.redirect_uri:
        payload["redirect_uri"] = args.redirect_uri
    if args.code_verifier:
        payload["code_verifier"] = args.code_verifier
    if args.scope:
        payload["scope"] = args.scope

    status, raw = _post_json(TOKEN_URL, payload, args.timeout)
    parsed = _parse_json(raw)
    output: dict[str, Any] = {
        "http_status": status,
        "request_url": TOKEN_URL,
        "response": parsed,
    }

    if isinstance(parsed, dict) and parsed.get("code") == 0 and args.emit_env:
        access_token = parsed.get("access_token")
        if access_token:
            output["export_env"] = f'$env:FEISHU_MCP_UAT="{access_token}"'
        refresh_token = parsed.get("refresh_token")
        if refresh_token:
            output["refresh_token_hint"] = "Store refresh_token securely; do not commit to code."

    if args.state_file and isinstance(parsed, dict):
        try:
            state = _load_state(args.state_file)
            state = _update_state_with_oauth_tokens(
                state=state,
                parsed=parsed,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=args.redirect_uri,
            )
            _save_state(args.state_file, state)
            output["state_file"] = args.state_file
            output["state_summary"] = {
                "app_id": state.get("app_id"),
                "scope": state.get("scope"),
                "uat_masked": _mask((state.get("uat") or {}).get("access_token") if isinstance(state.get("uat"), dict) else None),
                "refresh_masked": _mask((state.get("refresh") or {}).get("refresh_token") if isinstance(state.get("refresh"), dict) else None),
            }
        except Exception as exc:  # noqa: BLE001
            output["state_file_error"] = str(exc)

    _print_json(output, args.compact)

    if status >= 400:
        return 1
    if isinstance(parsed, dict) and parsed.get("code", 0) != 0:
        return 3
    return 0


def cmd_refresh_token(args: argparse.Namespace) -> int:
    try:
        client_id = _env_or_value(args.client_id, ENV_APP_ID, "--client-id")
        client_secret = _env_or_value(args.client_secret, ENV_APP_SECRET, "--client-secret")
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": args.refresh_token,
    }
    if args.scope:
        payload["scope"] = args.scope

    status, raw = _post_json(args.refresh_url, payload, args.timeout)
    parsed = _parse_json(raw)
    output: dict[str, Any] = {
        "http_status": status,
        "request_url": args.refresh_url,
        "response": parsed,
    }

    if isinstance(parsed, dict) and parsed.get("code") == 0 and args.emit_env:
        access_token = parsed.get("access_token")
        if access_token:
            output["export_env"] = f'$env:FEISHU_MCP_UAT="{access_token}"'

    if args.state_file and isinstance(parsed, dict):
        try:
            state = _load_state(args.state_file)
            state = _update_state_with_oauth_tokens(
                state=state,
                parsed=parsed,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=state.get("redirect_uri") if isinstance(state.get("redirect_uri"), str) else None,
            )
            _save_state(args.state_file, state)
            output["state_file"] = args.state_file
            output["state_summary"] = {
                "scope": state.get("scope"),
                "uat_masked": _mask((state.get("uat") or {}).get("access_token") if isinstance(state.get("uat"), dict) else None),
                "refresh_masked": _mask((state.get("refresh") or {}).get("refresh_token") if isinstance(state.get("refresh"), dict) else None),
            }
        except Exception as exc:  # noqa: BLE001
            output["state_file_error"] = str(exc)

    _print_json(output, args.compact)

    if status >= 400:
        return 1
    if isinstance(parsed, dict) and parsed.get("code", 0) != 0:
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feishu OAuth helper for user_access_token workflows.")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth-url", help="Generate authorize URL to obtain OAuth code.")
    auth.add_argument("--client-id", help=f"App ID. Fallback env: {ENV_APP_ID}.")
    auth.add_argument("--redirect-uri", required=True, help="Redirect URI configured in app security settings.")
    auth.add_argument("--scope", help="Space-separated scope string.")
    auth.add_argument("--state", help="Optional state. Random value if omitted.")
    auth.add_argument("--code-challenge", help="PKCE code_challenge.")
    auth.add_argument(
        "--code-challenge-method",
        default="S256",
        choices=("S256", "plain"),
        help="PKCE code_challenge_method.",
    )
    auth.add_argument("--compact", action="store_true", help="Print compact JSON.")
    auth.set_defaults(func=cmd_auth_url)

    exchange = sub.add_parser("exchange-code", help="Exchange authorization code for user_access_token.")
    exchange.add_argument("--client-id", help=f"App ID. Fallback env: {ENV_APP_ID}.")
    exchange.add_argument("--client-secret", help=f"App Secret. Fallback env: {ENV_APP_SECRET}.")
    exchange.add_argument("--code", required=True, help="Authorization code (single-use, short TTL).")
    exchange.add_argument("--redirect-uri", help="Must match authorize request if provided during authorization.")
    exchange.add_argument("--code-verifier", help="PKCE code_verifier.")
    exchange.add_argument("--scope", help="Optional narrowed scope (space-separated).")
    exchange.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    exchange.add_argument("--emit-env", action="store_true", help="Emit PowerShell export command when successful.")
    exchange.add_argument("--state-file", help="Optional JSON state file to persist app/UAT/refresh tokens.")
    exchange.add_argument("--compact", action="store_true", help="Print compact JSON.")
    exchange.set_defaults(func=cmd_exchange_code)

    refresh = sub.add_parser("refresh-token", help="Refresh user_access_token from refresh_token.")
    refresh.add_argument("--client-id", help=f"App ID. Fallback env: {ENV_APP_ID}.")
    refresh.add_argument("--client-secret", help=f"App Secret. Fallback env: {ENV_APP_SECRET}.")
    refresh.add_argument("--refresh-token", required=True, help="Refresh token value.")
    refresh.add_argument(
        "--refresh-url",
        default=REFRESH_URL,
        help=f"Refresh endpoint URL (default: {REFRESH_URL}).",
    )
    refresh.add_argument("--scope", help="Optional narrowed scope (space-separated).")
    refresh.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    refresh.add_argument("--emit-env", action="store_true", help="Emit PowerShell export command when successful.")
    refresh.add_argument("--state-file", help="Optional JSON state file to update after refresh.")
    refresh.add_argument("--compact", action="store_true", help="Print compact JSON.")
    refresh.set_defaults(func=cmd_refresh_token)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
