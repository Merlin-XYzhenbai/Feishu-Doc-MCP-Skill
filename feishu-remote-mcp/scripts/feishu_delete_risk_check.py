#!/usr/bin/env python3
"""Non-destructive risk check for Feishu document deletion requests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

MCP_URL = "https://mcp.feishu.cn/mcp"
ENV_UAT = "FEISHU_MCP_UAT"
ENV_TAT = "FEISHU_MCP_TAT"


def parse_target(raw: str) -> dict[str, str]:
    if "::" in raw:
        title, doc_id = raw.split("::", 1)
        title = title.strip()
        doc_id = doc_id.strip()
        if not title:
            raise ValueError(f"Invalid target '{raw}': empty title.")
        if not doc_id:
            raise ValueError(f"Invalid target '{raw}': empty doc_id after '::'.")
        return {"title": title, "doc_id": doc_id}
    title = raw.strip()
    if not title:
        raise ValueError("Target title cannot be empty.")
    return {"title": title}


def resolve_token(token_type: str, token: str | None) -> tuple[str, str]:
    if token:
        if token_type == "auto":
            if token.startswith("t-"):
                return token, "X-Lark-MCP-TAT"
            return token, "X-Lark-MCP-UAT"
        return (token, "X-Lark-MCP-UAT") if token_type == "uat" else (token, "X-Lark-MCP-TAT")

    if token_type == "uat":
        value = os.environ.get(ENV_UAT)
        if not value:
            raise ValueError(f"Set {ENV_UAT} or pass --token.")
        return value, "X-Lark-MCP-UAT"
    if token_type == "tat":
        value = os.environ.get(ENV_TAT)
        if not value:
            raise ValueError(f"Set {ENV_TAT} or pass --token.")
        return value, "X-Lark-MCP-TAT"

    tat = os.environ.get(ENV_TAT)
    if tat:
        return tat, "X-Lark-MCP-TAT"
    uat = os.environ.get(ENV_UAT)
    if uat:
        return uat, "X-Lark-MCP-UAT"
    raise ValueError(f"Set {ENV_UAT} or {ENV_TAT}, or pass --token.")


def mcp_call(
    token_header: str,
    token: str,
    method: str,
    params: dict[str, Any] | None,
    request_id: int,
) -> tuple[int, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params

    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header(token_header, token)
    req.add_header("X-Lark-MCP-Allowed-Tools", "search-doc,fetch-doc")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}
    except urllib.error.URLError as exc:
        return 0, {"transport_error": str(exc.reason)}


def extract_items(resp_obj: Any) -> list[dict[str, Any]]:
    if not isinstance(resp_obj, dict):
        return []
    result = resp_obj.get("result")
    if not isinstance(result, dict):
        return []
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return []
    first = content[0]
    if not isinstance(first, dict):
        return []
    text = first.get("text")
    if not isinstance(text, str):
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    data = parsed.get("data") if isinstance(parsed, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def normalize_url(item: dict[str, Any]) -> str:
    url = item.get("url")
    if isinstance(url, str) and url:
        return url
    doc_id = item.get("id")
    if isinstance(doc_id, str) and doc_id:
        return f"https://www.feishu.cn/docx/{doc_id}"
    return ""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Non-destructive delete risk check for target docs.")
    parser.add_argument("--token-type", choices=("auto", "uat", "tat"), default="auto")
    parser.add_argument("--token", help="Token value, optional.")
    parser.add_argument(
        "--target",
        action="append",
        required=True,
        help="Target format: 'title' or 'title::doc_id' for strict matching.",
    )
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)

    try:
        token, token_header = resolve_token(args.token_type, args.token)
        targets = [parse_target(item) for item in args.target]
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "policy": "Deletion is high risk. Recommend user manual deletion in Feishu UI.",
        "manual_delete_recommended": True,
        "token_header": token_header,
        "targets": targets,
        "results": [],
    }

    rid = 1
    for target in targets:
        title = target["title"]
        doc_id_expect = target.get("doc_id")
        st, resp = mcp_call(
            token_header=token_header,
            token=token,
            method="tools/call",
            params={"name": "search-doc", "arguments": {"query": title}},
            request_id=rid,
        )
        rid += 1

        items = extract_items(resp)
        exact_title = [item for item in items if item.get("title") == title]
        strict_match = [
            item
            for item in exact_title
            if doc_id_expect is None or item.get("id") == doc_id_expect
        ]
        candidates = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "url": normalize_url(item),
                "owner_name": item.get("owner_name"),
                "update_time": item.get("update_time"),
            }
            for item in strict_match
        ]
        report["results"].append(
            {
                "target": target,
                "search_http": st,
                "strict_match_count": len(candidates),
                "strict_matches": candidates,
            }
        )

    report["manual_steps"] = [
        "Open each matched URL in Feishu.",
        "Verify title, owner, and latest update time.",
        "Delete manually in Feishu UI to avoid accidental loss.",
    ]

    if args.compact:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
