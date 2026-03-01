#!/usr/bin/env python3
"""Deterministic preset workflows for Feishu remote MCP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

DEFAULT_URL = "https://mcp.feishu.cn/mcp"
ENV_UAT = "FEISHU_MCP_UAT"
ENV_TAT = "FEISHU_MCP_TAT"

DEFAULT_ALLOWED_TOOLS = [
    "search-user",
    "get-user",
    "fetch-file",
    "search-doc",
    "create-doc",
    "fetch-doc",
    "update-doc",
    "list-docs",
    "get-comments",
    "add-comments",
]


def parse_key_value(item: str) -> tuple[str, Any]:
    if "=" not in item:
        raise ValueError(f"Invalid --set value '{item}', expected key=value.")
    key, raw = item.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError(f"Invalid --set value '{item}', key is empty.")
    raw = raw.strip()
    if raw.startswith("json:"):
        try:
            return key, json.loads(raw[5:])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in --set {item}: {exc}") from exc
    return key, raw


def parse_set_values(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key, value = parse_key_value(item)
        result[key] = value
    return result


def parse_json_object(raw: str, field: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field} must decode to an object.")
    return parsed


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
    raise ValueError(f"Set {ENV_TAT} or {ENV_UAT}, or pass --token.")


def normalize_allowlist(raw: str | None, fallback: list[str] | None = None) -> str:
    if raw is None:
        values = fallback or []
    else:
        values = [item.strip() for item in raw.split(",") if item.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return ",".join(deduped)


def http_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> tuple[int, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)

    raw = ""
    status = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return 0, {"transport_error": str(exc.reason)}

    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw}


def summarize_rpc(status: int, data: Any) -> dict[str, Any]:
    rpc_error = None
    is_tool_error = False
    if isinstance(data, dict):
        rpc_error = data.get("error")
        result = data.get("result")
        if isinstance(result, dict):
            is_tool_error = bool(result.get("isError"))
    return {
        "http_status": status,
        "ok": status < 400 and rpc_error is None and not is_tool_error,
        "rpc_error": rpc_error,
        "is_tool_error": is_tool_error,
    }


class MCPClient:
    def __init__(
        self,
        url: str,
        token: str,
        auth_header: str,
        timeout: float,
        request_id_start: int,
        default_allowlist: str,
    ) -> None:
        self.url = url
        self.token = token
        self.auth_header = auth_header
        self.timeout = timeout
        self._request_id = request_id_start
        self.default_allowlist = default_allowlist

    def _next_id(self) -> int:
        val = self._request_id
        self._request_id += 1
        return val

    def call(self, method: str, params: dict[str, Any] | None, allowlist: str | None = None) -> tuple[int, Any]:
        headers = {self.auth_header: self.token}
        effective_allowlist = allowlist if allowlist is not None else self.default_allowlist
        if effective_allowlist:
            headers["X-Lark-MCP-Allowed-Tools"] = effective_allowlist
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            payload["params"] = params
        return http_post_json(self.url, headers, payload, self.timeout)

    def initialize(self, allowlist: str | None = None) -> tuple[int, Any]:
        return self.call("initialize", None, allowlist)

    def tools_list(self, allowlist: str | None = None) -> tuple[int, Any]:
        return self.call("tools/list", None, allowlist)

    def tool_call(self, name: str, arguments: dict[str, Any], allowlist: str | None = None) -> tuple[int, Any]:
        params = {"name": name, "arguments": arguments}
        return self.call("tools/call", params, allowlist)


def extract_tools(tools_list_resp: Any) -> list[dict[str, Any]]:
    if not isinstance(tools_list_resp, dict):
        return []
    result = tools_list_resp.get("result")
    if not isinstance(result, dict):
        return []
    tools = result.get("tools")
    if not isinstance(tools, list):
        return []
    return [tool for tool in tools if isinstance(tool, dict)]


def find_tool(tools: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for tool in tools:
        if tool.get("name") == name:
            return tool
    return None


def infer_value_for_required(key: str, schema: dict[str, Any], context: dict[str, Any]) -> Any:
    lower = key.lower()
    value_type = schema.get("type") if isinstance(schema, dict) else None

    if any(token in lower for token in ("docid", "doc_id", "document_id", "doc_token", "doctoken")):
        if context.get("doc_id"):
            return context["doc_id"]
    if "title" in lower or lower.endswith("name"):
        if context.get("title"):
            return context["title"]
        return f"MCP Preset {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    if any(token in lower for token in ("markdown", "content", "text", "body", "message")):
        if context.get("text"):
            return context["text"]
        return "Generated by feishu_mcp_presets."
    if any(token in lower for token in ("comment", "reply")):
        if context.get("comment"):
            return context["comment"]
        return "Automated comment from preset workflow."
    if lower == "elements":
        text = context.get("comment") or context.get("text") or "Automated comment from preset workflow."
        return [{"type": "text", "text": text}]
    if any(token in lower for token in ("keyword", "query", "search")):
        if context.get("query"):
            return context["query"]
        return "test"

    if value_type == "string":
        return "test"
    if value_type == "integer":
        return 1
    if value_type == "number":
        return 1
    if value_type == "boolean":
        return False
    if value_type == "array":
        return []
    if value_type == "object":
        return {}
    return "test"


def build_arguments(tool: dict[str, Any], explicit: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        schema = {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required")
    if not isinstance(required, list):
        required = []

    args = dict(explicit)
    missing: list[str] = []
    for key in required:
        if key in args:
            continue
        prop_schema = properties.get(key) if isinstance(properties.get(key), dict) else {}
        inferred = infer_value_for_required(key, prop_schema, context)
        if inferred is None:
            missing.append(key)
            continue
        args[key] = inferred
    return args, missing


def parse_content_json(result_obj: dict[str, Any]) -> dict[str, Any]:
    content = result_obj.get("content")
    if not isinstance(content, list) or not content:
        return {}
    first = content[0]
    if not isinstance(first, dict):
        return {}
    text = first.get("text")
    if not isinstance(text, str):
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text_preview": text[:800]}
    if isinstance(parsed, dict):
        return parsed
    return {"parsed": parsed}


def summarize_comments_payload(parsed_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(parsed_result, dict):
        return {}

    payload = parsed_result.get("data") if isinstance(parsed_result.get("data"), dict) else parsed_result
    comments = payload.get("comments") if isinstance(payload, dict) else None
    if not isinstance(comments, list):
        return {}

    whole_count = 0
    segment_count = 0
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        ctype = comment.get("type")
        if ctype == "whole":
            whole_count += 1
        elif ctype == "segment":
            segment_count += 1

    return {
        "comment_count": len(comments),
        "whole_count": whole_count,
        "segment_count": segment_count,
        "has_more": payload.get("has_more"),
        "page_token": payload.get("page_token"),
    }


def diagnose_get_comments_error(result: dict[str, Any]) -> dict[str, Any] | None:
    parsed = result.get("parsed_result")
    if not isinstance(parsed, dict):
        return None
    text_preview = parsed.get("text_preview")
    if not isinstance(text_preview, str):
        return None

    lower = text_preview.lower()
    if "authentication token expired" in lower or "errorcode=99991677" in lower:
        return {
            "category": "token_expired",
            "message": "Current UAT is expired.",
            "next_steps": [
                "Refresh UAT with scripts/feishu_token_store.py refresh-uat.",
                "If refresh fails, run OAuth authorize + exchange-code again.",
                "Retry doc-comments after token update.",
            ],
        }
    if "contact:contact.base:readonly" in text_preview:
        return {
            "category": "missing_user_scope",
            "required_scope": "contact:contact.base:readonly",
            "message": "Current UAT does not include required user scope for get-comments.",
            "next_steps": [
                "Re-authorize UAT with scope contact:contact.base:readonly.",
                "Exchange new authorization code and replace stored UAT/refresh token.",
                "Retry doc-comments after token rotation.",
            ],
            "note": "Refreshing existing refresh_token cannot add new permissions outside prior user consent.",
        }
    return {
        "category": "tool_error",
        "message": text_preview[:500],
    }


def run_doc_comments(
    client: MCPClient,
    doc_id: str,
    comment_type: str,
    page_size: int | None,
    page_token: str | None,
    explicit_sets: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    explicit = {"doc_id": doc_id, "comment_type": comment_type}
    if page_size is not None:
        explicit["page_size"] = page_size
    if page_token:
        explicit["page_token"] = page_token
    explicit.update(explicit_sets)

    code, result = run_tool_with_schema(
        client=client,
        tool_name="get-comments",
        explicit_args=explicit,
        context={"doc_id": doc_id},
        allowlist="get-comments",
    )
    summary: dict[str, Any] = {"result": result}
    parsed = result.get("parsed_result") if isinstance(result, dict) else None
    if isinstance(parsed, dict):
        summary["comments_summary"] = summarize_comments_payload(parsed)

    call = result.get("tool_call") if isinstance(result, dict) else None
    if isinstance(call, dict) and not bool(call.get("ok")):
        diagnostic = diagnose_get_comments_error(result)
        if diagnostic:
            summary["diagnostic"] = diagnostic
    return code, summary


def run_catalog(client: MCPClient, allowlist: str) -> tuple[int, dict[str, Any]]:
    st_init, init_data = client.initialize(allowlist)
    st_list, list_data = client.tools_list(allowlist)
    tools = extract_tools(list_data)

    catalog = []
    for tool in tools:
        name = tool.get("name")
        schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        catalog.append(
            {
                "name": name,
                "required": required,
                "properties": sorted(props.keys()),
                "description": tool.get("description"),
            }
        )
    summary = {
        "initialize": summarize_rpc(st_init, init_data),
        "tools_list": summarize_rpc(st_list, list_data),
        "tool_count": len(catalog),
        "catalog": catalog,
    }
    ok = summary["initialize"]["ok"] and summary["tools_list"]["ok"]
    return (0 if ok else 1), summary


def run_smoke(client: MCPClient, allowlist: str) -> tuple[int, dict[str, Any]]:
    st_init, init_data = client.initialize(allowlist)
    st_list, list_data = client.tools_list(allowlist)
    tools = extract_tools(list_data)
    summary = {
        "initialize": summarize_rpc(st_init, init_data),
        "tools_list": summarize_rpc(st_list, list_data),
        "tool_count": len(tools),
        "tool_names": [tool.get("name") for tool in tools],
        "server_info": init_data.get("result", {}).get("serverInfo") if isinstance(init_data, dict) else None,
    }
    ok = summary["initialize"]["ok"] and summary["tools_list"]["ok"]
    return (0 if ok else 1), summary


def run_tool_with_schema(
    client: MCPClient,
    tool_name: str,
    explicit_args: dict[str, Any],
    context: dict[str, Any],
    allowlist: str,
) -> tuple[int, dict[str, Any]]:
    st_list, list_data = client.tools_list(allowlist)
    list_summary = summarize_rpc(st_list, list_data)
    tools = extract_tools(list_data)
    tool = find_tool(tools, tool_name)
    if not tool:
        return 1, {
            "tools_list": list_summary,
            "error": f"Tool '{tool_name}' not found in tools/list response.",
            "tool_names": [item.get("name") for item in tools],
        }

    args, missing = build_arguments(tool, explicit_args, context)
    if missing:
        return 1, {
            "tools_list": list_summary,
            "error": "Missing required fields after inference.",
            "missing_required_fields": missing,
            "arguments_generated": args,
        }

    st_call, call_data = client.tool_call(tool_name, args, allowlist)
    call_summary = summarize_rpc(st_call, call_data)
    parsed = {}
    if isinstance(call_data, dict) and isinstance(call_data.get("result"), dict):
        parsed = parse_content_json(call_data["result"])

    result = {
        "tools_list": list_summary,
        "tool_call": call_summary,
        "tool": tool_name,
        "arguments": args,
        "parsed_result": parsed,
    }
    return (0 if call_summary["ok"] else 1), result


def run_doc_roundtrip(
    client: MCPClient,
    title: str,
    markdown: str,
    comment: str | None,
    explicit_sets: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    summary: dict[str, Any] = {"steps": []}
    exit_code = 0

    # create
    create_allow = "create-doc,fetch-doc,add-comments"
    explicit_create = {"title": title, "markdown": markdown}
    explicit_create.update(explicit_sets)
    rc, create_result = run_tool_with_schema(
        client=client,
        tool_name="create-doc",
        explicit_args=explicit_create,
        context={"title": title, "text": markdown},
        allowlist=create_allow,
    )
    summary["steps"].append({"step": "create-doc", "result": create_result})
    if rc != 0:
        return 1, summary

    parsed = create_result.get("parsed_result", {})
    doc_id = parsed.get("doc_id") or parsed.get("docID") or parsed.get("docId")
    doc_url = parsed.get("doc_url") or parsed.get("url")
    summary["doc_id"] = doc_id
    summary["doc_url"] = doc_url
    if not doc_id:
        summary["warning"] = "create-doc succeeded but doc_id was not found in parsed_result."
        return 1, summary

    # fetch
    rc, fetch_result = run_tool_with_schema(
        client=client,
        tool_name="fetch-doc",
        explicit_args=explicit_sets,
        context={"doc_id": doc_id},
        allowlist="fetch-doc",
    )
    summary["steps"].append({"step": "fetch-doc", "result": fetch_result})
    if rc != 0:
        exit_code = 1

    # comment optional
    if comment:
        explicit_comment = {
            "doc_id": doc_id,
            "elements": [{"type": "text", "text": comment}],
        }
        explicit_comment.update(explicit_sets)
        rc, comment_result = run_tool_with_schema(
            client=client,
            tool_name="add-comments",
            explicit_args=explicit_comment,
            context={"doc_id": doc_id, "comment": comment, "text": comment},
            allowlist="add-comments",
        )
        summary["steps"].append({"step": "add-comments", "result": comment_result})
        if rc != 0:
            exit_code = 1

    return exit_code, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic preset workflows for Feishu MCP.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint URL (default: {DEFAULT_URL})")
    parser.add_argument("--token-type", choices=("auto", "uat", "tat"), default="auto")
    parser.add_argument("--token", help="Token value. If omitted, read from FEISHU_MCP_UAT or FEISHU_MCP_TAT.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--request-id-start", type=int, default=1)
    parser.add_argument("--compact", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="Run initialize + tools/list.")
    smoke.add_argument("--allowed-tools", help="Comma list for allowlist header.")

    catalog = sub.add_parser("catalog", help="Export tool catalog (names + required fields).")
    catalog.add_argument("--allowed-tools", help="Comma list for allowlist header.")

    tool_call = sub.add_parser("tool-call", help="Call any tool with schema-aware argument inference.")
    tool_call.add_argument("--tool", required=True, help="Tool name.")
    tool_call.add_argument("--allowed-tools", help="Comma list for allowlist header. Default: tool name.")
    tool_call.add_argument("--set", action="append", default=[], help="Explicit args: key=value or key=json:{...}")
    tool_call.add_argument("--arguments-json", help="Raw JSON object. Overrides --set.")
    tool_call.add_argument("--doc-id", help="Context value for doc-related fields.")
    tool_call.add_argument("--text", help="Context value for content/text fields.")
    tool_call.add_argument("--query", help="Context value for search fields.")

    doc_create = sub.add_parser("doc-create", help="Create a document via create-doc.")
    doc_create.add_argument("--title", default=f"MCP Preset {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    doc_create.add_argument("--markdown", default="Created by feishu_mcp_presets doc-create workflow.")
    doc_create.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    doc_read = sub.add_parser("doc-read", help="Read a document via fetch-doc.")
    doc_read.add_argument("--doc-id", required=True)
    doc_read.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    doc_comment = sub.add_parser("doc-comment", help="Add document comment via add-comments.")
    doc_comment.add_argument("--doc-id", required=True)
    doc_comment.add_argument("--comment", required=True)
    doc_comment.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    doc_comments = sub.add_parser("doc-comments", help="Read comments via get-comments with diagnostics.")
    doc_comments.add_argument("--doc-id", required=True)
    doc_comments.add_argument("--comment-type", choices=("all", "whole", "segment"), default="all")
    doc_comments.add_argument("--page-size", type=int, help="Optional page size (1-100).")
    doc_comments.add_argument("--page-token", help="Optional page token for pagination.")
    doc_comments.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    doc_roundtrip = sub.add_parser("doc-roundtrip", help="Create doc then fetch doc and optional comment.")
    doc_roundtrip.add_argument("--title", default=f"MCP Roundtrip {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    doc_roundtrip.add_argument("--markdown", default="Created by doc-roundtrip workflow.")
    doc_roundtrip.add_argument("--comment", help="Optional comment text to post.")
    doc_roundtrip.add_argument("--set", action="append", default=[], help="Extra explicit args for all steps.")

    user_self = sub.add_parser("user-self", help="Get current user via get-user.")
    user_self.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    user_search = sub.add_parser("user-search", help="Search user via search-user.")
    user_search.add_argument("--query", required=True)
    user_search.add_argument("--set", action="append", default=[], help="Extra explicit args.")

    return parser


def print_output(data: dict[str, Any], compact: bool) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=None if compact else 2)
    try:
        print(text)
        return
    except UnicodeEncodeError:
        # Windows GBK terminals may fail on emoji; fallback keeps output machine-readable.
        pass

    fallback = json.dumps(data, ensure_ascii=True, indent=None if compact else 2)
    print(fallback)


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        token, auth_header = resolve_token(args.token_type, args.token)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    default_allow = normalize_allowlist(None, DEFAULT_ALLOWED_TOOLS)
    client = MCPClient(
        url=args.url,
        token=token,
        auth_header=auth_header,
        timeout=args.timeout,
        request_id_start=args.request_id_start,
        default_allowlist=default_allow,
    )

    output: dict[str, Any] = {"command": args.command, "auth_header": auth_header}
    code = 1

    try:
        if args.command == "smoke":
            allow = normalize_allowlist(args.allowed_tools, DEFAULT_ALLOWED_TOOLS)
            code, result = run_smoke(client, allow)
            output["result"] = result
        elif args.command == "catalog":
            allow = normalize_allowlist(args.allowed_tools, DEFAULT_ALLOWED_TOOLS)
            code, result = run_catalog(client, allow)
            output["result"] = result
        elif args.command == "tool-call":
            allow = normalize_allowlist(args.allowed_tools, [args.tool])
            explicit = (
                parse_json_object(args.arguments_json, "--arguments-json")
                if args.arguments_json
                else parse_set_values(args.set)
            )
            context = {"doc_id": args.doc_id, "text": args.text, "query": args.query}
            code, result = run_tool_with_schema(client, args.tool, explicit, context, allow)
            output["result"] = result
        elif args.command == "doc-create":
            explicit = parse_set_values(args.set)
            code, result = run_tool_with_schema(
                client,
                "create-doc",
                explicit_args={"title": args.title, "markdown": args.markdown, **explicit},
                context={"title": args.title, "text": args.markdown},
                allowlist="create-doc",
            )
            output["result"] = result
        elif args.command == "doc-read":
            explicit = parse_set_values(args.set)
            code, result = run_tool_with_schema(
                client,
                "fetch-doc",
                explicit_args=explicit,
                context={"doc_id": args.doc_id},
                allowlist="fetch-doc",
            )
            output["result"] = result
        elif args.command == "doc-comment":
            explicit = parse_set_values(args.set)
            explicit_comment = {
                "doc_id": args.doc_id,
                "elements": [{"type": "text", "text": args.comment}],
                **explicit,
            }
            code, result = run_tool_with_schema(
                client,
                "add-comments",
                explicit_args=explicit_comment,
                context={"doc_id": args.doc_id, "comment": args.comment, "text": args.comment},
                allowlist="add-comments",
            )
            output["result"] = result
        elif args.command == "doc-comments":
            explicit = parse_set_values(args.set)
            code, result = run_doc_comments(
                client=client,
                doc_id=args.doc_id,
                comment_type=args.comment_type,
                page_size=args.page_size,
                page_token=args.page_token,
                explicit_sets=explicit,
            )
            output["result"] = result
        elif args.command == "doc-roundtrip":
            explicit = parse_set_values(args.set)
            code, result = run_doc_roundtrip(client, args.title, args.markdown, args.comment, explicit)
            output["result"] = result
        elif args.command == "user-self":
            explicit = parse_set_values(args.set)
            code, result = run_tool_with_schema(
                client,
                "get-user",
                explicit_args=explicit,
                context={},
                allowlist="get-user",
            )
            output["result"] = result
        elif args.command == "user-search":
            explicit = parse_set_values(args.set)
            code, result = run_tool_with_schema(
                client,
                "search-user",
                explicit_args=explicit,
                context={"query": args.query, "text": args.query},
                allowlist="search-user",
            )
            output["result"] = result
        else:
            output["error"] = f"Unsupported command: {args.command}"
            code = 2
    except ValueError as exc:
        output["error"] = str(exc)
        code = 2

    print_output(output, args.compact)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
