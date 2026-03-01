#!/usr/bin/env python3
"""Manage Feishu app credentials and rotating tokens in a local JSON file."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
TAT_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_after(seconds: int | None) -> str | None:
    if not isinstance(seconds, int):
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def load_store(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Store file must be a JSON object.")
    return data


def save_store(path: str, data: dict[str, Any]) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def post_json(url: str, payload: dict[str, Any], timeout: float = 30.0) -> tuple[int, Any]:
    req = urllib.request.Request(url=url, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def mask(token: str | None) -> str:
    if not token:
        return ""
    if len(token) <= 16:
        return token[:4] + "..."
    return token[:8] + "..." + token[-8:]


def build_summary(data: dict[str, Any]) -> dict[str, Any]:
    uat = data.get("uat") if isinstance(data.get("uat"), dict) else {}
    refresh = data.get("refresh") if isinstance(data.get("refresh"), dict) else {}
    tat = data.get("tat") if isinstance(data.get("tat"), dict) else {}
    return {
        "app_id": data.get("app_id"),
        "redirect_uri": data.get("redirect_uri"),
        "scope": data.get("scope"),
        "uat": {
            "masked": mask(uat.get("access_token") if isinstance(uat.get("access_token"), str) else None),
            "expires_at": uat.get("expires_at"),
            "updated_at": uat.get("updated_at"),
        },
        "refresh": {
            "masked": mask(refresh.get("refresh_token") if isinstance(refresh.get("refresh_token"), str) else None),
            "expires_at": refresh.get("expires_at"),
            "updated_at": refresh.get("updated_at"),
        },
        "tat": {
            "masked": mask(tat.get("access_token") if isinstance(tat.get("access_token"), str) else None),
            "expires_at": tat.get("expires_at"),
            "updated_at": tat.get("updated_at"),
        },
    }


def cmd_init(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    store["app_id"] = args.app_id
    store["app_secret"] = args.app_secret
    if args.redirect_uri:
        store["redirect_uri"] = args.redirect_uri
    if args.scope:
        store["scope"] = args.scope
    store["updated_at"] = iso_now()
    save_store(args.file, store)
    print(json.dumps({"file": args.file, "summary": build_summary(store)}, ensure_ascii=False, indent=2))
    return 0


def cmd_exchange_code(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    app_id = args.app_id or store.get("app_id")
    app_secret = args.app_secret or store.get("app_secret")
    redirect_uri = args.redirect_uri or store.get("redirect_uri")
    if not app_id or not app_secret:
        print("[error] app_id/app_secret missing. Run init or pass --app-id --app-secret.", file=sys.stderr)
        return 2
    payload: dict[str, Any] = {
        "grant_type": "authorization_code",
        "client_id": app_id,
        "client_secret": app_secret,
        "code": args.code,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri
    if args.scope:
        payload["scope"] = args.scope

    status, resp = post_json(TOKEN_URL, payload, args.timeout)
    output: dict[str, Any] = {"http_status": status, "response": resp}
    if isinstance(resp, dict) and resp.get("code") == 0:
        store["app_id"] = app_id
        store["app_secret"] = app_secret
        if redirect_uri:
            store["redirect_uri"] = redirect_uri
        if isinstance(resp.get("scope"), str):
            store["scope"] = resp["scope"]
        store["uat"] = {
            "access_token": resp.get("access_token"),
            "expires_in": resp.get("expires_in"),
            "expires_at": iso_after(resp.get("expires_in") if isinstance(resp.get("expires_in"), int) else None),
            "token_type": resp.get("token_type"),
            "updated_at": iso_now(),
        }
        if isinstance(resp.get("refresh_token"), str):
            store["refresh"] = {
                "refresh_token": resp.get("refresh_token"),
                "expires_in": resp.get("refresh_token_expires_in"),
                "expires_at": iso_after(
                    resp.get("refresh_token_expires_in")
                    if isinstance(resp.get("refresh_token_expires_in"), int)
                    else None
                ),
                "updated_at": iso_now(),
            }
        store["updated_at"] = iso_now()
        save_store(args.file, store)
        output["summary"] = build_summary(store)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if status >= 400:
        return 1
    if isinstance(resp, dict) and resp.get("code", 0) != 0:
        return 3
    return 0


def cmd_refresh_uat(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    app_id = args.app_id or store.get("app_id")
    app_secret = args.app_secret or store.get("app_secret")
    refresh_token = args.refresh_token
    if not refresh_token and isinstance(store.get("refresh"), dict):
        refresh_token = store["refresh"].get("refresh_token")
    if not app_id or not app_secret:
        print("[error] app_id/app_secret missing. Run init or pass values.", file=sys.stderr)
        return 2
    if not refresh_token:
        print("[error] refresh_token missing. Pass --refresh-token or store one in file.", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "grant_type": "refresh_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "refresh_token": refresh_token,
    }
    if args.scope:
        payload["scope"] = args.scope

    status, resp = post_json(TOKEN_URL, payload, args.timeout)
    output: dict[str, Any] = {"http_status": status, "response": resp}
    if isinstance(resp, dict) and resp.get("code") == 0:
        store["app_id"] = app_id
        store["app_secret"] = app_secret
        if isinstance(resp.get("scope"), str):
            store["scope"] = resp["scope"]
        store["uat"] = {
            "access_token": resp.get("access_token"),
            "expires_in": resp.get("expires_in"),
            "expires_at": iso_after(resp.get("expires_in") if isinstance(resp.get("expires_in"), int) else None),
            "token_type": resp.get("token_type"),
            "updated_at": iso_now(),
        }
        if isinstance(resp.get("refresh_token"), str):
            store["refresh"] = {
                "refresh_token": resp.get("refresh_token"),
                "expires_in": resp.get("refresh_token_expires_in"),
                "expires_at": iso_after(
                    resp.get("refresh_token_expires_in")
                    if isinstance(resp.get("refresh_token_expires_in"), int)
                    else None
                ),
                "updated_at": iso_now(),
            }
        store["updated_at"] = iso_now()
        save_store(args.file, store)
        output["summary"] = build_summary(store)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if status >= 400:
        return 1
    if isinstance(resp, dict) and resp.get("code", 0) != 0:
        return 3
    return 0


def cmd_fetch_tat(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    app_id = args.app_id or store.get("app_id")
    app_secret = args.app_secret or store.get("app_secret")
    if not app_id or not app_secret:
        print("[error] app_id/app_secret missing. Run init or pass values.", file=sys.stderr)
        return 2
    payload = {"app_id": app_id, "app_secret": app_secret}
    status, resp = post_json(TAT_URL, payload, args.timeout)
    output: dict[str, Any] = {"http_status": status, "response": resp}
    if isinstance(resp, dict) and resp.get("code") == 0:
        expire = resp.get("expire")
        store["tat"] = {
            "access_token": resp.get("tenant_access_token"),
            "expires_in": expire,
            "expires_at": iso_after(expire if isinstance(expire, int) else None),
            "updated_at": iso_now(),
        }
        store["updated_at"] = iso_now()
        save_store(args.file, store)
        output["summary"] = build_summary(store)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if status >= 400:
        return 1
    if isinstance(resp, dict) and resp.get("code", 0) != 0:
        return 3
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    print(json.dumps({"file": args.file, "summary": build_summary(store)}, ensure_ascii=False, indent=2))
    return 0


def cmd_print_env(args: argparse.Namespace) -> int:
    store = load_store(args.file)
    if args.token_type == "uat":
        token = (store.get("uat") or {}).get("access_token") if isinstance(store.get("uat"), dict) else None
        if not token:
            print("[error] uat.access_token not found in store.", file=sys.stderr)
            return 2
        print(f'$env:FEISHU_MCP_UAT="{token}"')
        return 0
    token = (store.get("tat") or {}).get("access_token") if isinstance(store.get("tat"), dict) else None
    if not token:
        print("[error] tat.access_token not found in store.", file=sys.stderr)
        return 2
    print(f'$env:FEISHU_MCP_TAT="{token}"')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Store and rotate Feishu OAuth/TAT tokens in JSON.")
    parser.add_argument("--file", default="config/feishu-auth.local.json", help="Token store JSON file path.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize store with app credentials.")
    init.add_argument("--app-id", required=True)
    init.add_argument("--app-secret", required=True)
    init.add_argument("--redirect-uri")
    init.add_argument("--scope")
    init.set_defaults(func=cmd_init)

    exchange = sub.add_parser("exchange-code", help="Exchange OAuth code and persist UAT/refresh token.")
    exchange.add_argument("--code", required=True)
    exchange.add_argument("--app-id")
    exchange.add_argument("--app-secret")
    exchange.add_argument("--redirect-uri")
    exchange.add_argument("--scope")
    exchange.add_argument("--timeout", type=float, default=30.0)
    exchange.set_defaults(func=cmd_exchange_code)

    refresh = sub.add_parser("refresh-uat", help="Refresh UAT using refresh_token from store.")
    refresh.add_argument("--refresh-token", help="Optional override refresh token.")
    refresh.add_argument("--app-id")
    refresh.add_argument("--app-secret")
    refresh.add_argument("--scope")
    refresh.add_argument("--timeout", type=float, default=30.0)
    refresh.set_defaults(func=cmd_refresh_uat)

    tat = sub.add_parser("fetch-tat", help="Fetch tenant_access_token and persist it.")
    tat.add_argument("--app-id")
    tat.add_argument("--app-secret")
    tat.add_argument("--timeout", type=float, default=30.0)
    tat.set_defaults(func=cmd_fetch_tat)

    show = sub.add_parser("show", help="Show masked store summary.")
    show.set_defaults(func=cmd_show)

    export_env = sub.add_parser("print-env", help="Print PowerShell env export command for token.")
    export_env.add_argument("--token-type", choices=("uat", "tat"), required=True)
    export_env.set_defaults(func=cmd_print_env)

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
