---
name: feishu-remote-mcp
description: Integrate Feishu official remote MCP service into developer agents through HTTP JSON-RPC with UAT or TAT authentication, tool allowlists, and robust error handling. Use when building or operating agent workflows in OpenClaw, Claude Code, or Codex that need Feishu user lookup, cloud document search/read/write, comments, and file fetch capabilities, and when packaging this integration as a reusable skill.
---

# Feishu Remote MCP

## Overview

Connect directly to Feishu-hosted MCP (`https://mcp.feishu.cn/mcp`) without local MCP server deployment. Use this skill to plan permissions, configure authentication, run smoke tests, and call Feishu tools from agent code safely.

When collaborating with weaker agents, use preset scripts first and avoid free-form tool calling.

## Workflow

1. Run UAT first for initial integration.
- Use OAuth authorization code flow to get `user_access_token`.
- Use UAT to validate user-scope visibility and tool permissions quickly.
- Follow [`references/uat-first-runbook.md`](references/uat-first-runbook.md).

1. Expand to TAT only after UAT smoke tests pass.
- Use `tenant_access_token` for server-to-server automation where app identity is required.

1. Apply minimum required permissions for every planned MCP tool.
- Map tools to permissions with [`references/integration-checklist.md`](references/integration-checklist.md).
- Request all required scopes before runtime tests.

1. Restrict available tools per request.
- Set `X-Lark-MCP-Allowed-Tools` to the smallest tool list needed by the current task.
- Do not omit this header, or tool discovery and calls will fail.

1. Validate connection with a two-step smoke test.
- Run `initialize`.
- Run `tools/list` with the same allowed-tools set.

1. Call business tools via `tools/call` and handle two error layers.
- Handle top-level JSON-RPC `error`.
- Handle tool-level `result.isError == true` even when HTTP status is `200`.

1. Avoid brittle parsing.
- Treat tool input and output fields as changeable.
- Parse only fields you need; keep graceful fallbacks.

1. Handle deletion requests with strict risk policy.
- 当要删除文档时，提示用户风险，并建议用户自己来删。
- Run non-destructive precheck first with [`scripts/feishu_delete_risk_check.py`](scripts/feishu_delete_risk_check.py).
- Only continue after user reconfirms exact targets.

## Quick Commands

### UAT OAuth and Token Setup

Use [`scripts/feishu_uat_oauth.py`](scripts/feishu_uat_oauth.py) to generate OAuth authorize URL and exchange code.
Use [`scripts/feishu_oauth_callback_server.py`](scripts/feishu_oauth_callback_server.py) if you want automatic local callback capture.
Use [`scripts/feishu_token_store.py`](scripts/feishu_token_store.py) for weak-agent friendly JSON token storage and refresh rotation.

```bash
# 0) App credentials
$env:FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxx"

# 1) Generate authorize URL
python scripts/feishu_uat_oauth.py `
  auth-url `
  --redirect-uri "http://localhost:8080/callback" `
  --scope "offline_access docx:document:readonly"

# Optional: start callback listener first
python scripts/feishu_oauth_callback_server.py `
  --host localhost `
  --port 8080 `
  --path /callback

# 2) Exchange authorization code for UAT
python scripts/feishu_uat_oauth.py `
  exchange-code `
  --code "paste_code_here" `
  --redirect-uri "http://localhost:8080/callback" `
  --state-file "config/feishu-auth.local.json" `
  --emit-env

# 3) Refresh UAT from JSON store (rotates refresh_token)
python scripts/feishu_token_store.py `
  --file "config/feishu-auth.local.json" `
  refresh-uat
```

### Preset MCP Workflows (Recommended for Weaker Agents)

Use [`scripts/feishu_mcp_presets.py`](scripts/feishu_mcp_presets.py) for deterministic flows.

```bash
# PowerShell: set one token (UAT first)
$env:FEISHU_MCP_UAT="u-gxxxxxxxxxxxxxxxxxxxxx"

# 1) smoke test (initialize + tools/list)
python scripts/feishu_mcp_presets.py `
  --token-type uat `
  smoke

# 2) export tool catalog (required fields included)
python scripts/feishu_mcp_presets.py `
  --token-type uat `
  catalog

# 3) create a document
python scripts/feishu_mcp_presets.py `
  --token-type uat `
  doc-create `
  --title "Agent Fixed Flow Test" `
  --markdown "Created by preset workflow."

# 4) roundtrip document test
python scripts/feishu_mcp_presets.py `
  --token-type uat `
  doc-roundtrip `
  --title "Roundtrip Test" `
  --markdown "Create + fetch + optional comment." `
  --comment "Roundtrip comment"

# 5) read comments with diagnostics (whole + segment)
python scripts/feishu_mcp_presets.py `
  --token-type uat `
  doc-comments `
  --doc-id "doccnxxxxxxxxxxxx" `
  --comment-type all

# If diagnostic.category=missing_user_scope:
# Re-authorize UAT with contact:contact.base:readonly, then exchange code again.

# 6) deletion risk precheck (non-destructive, manual delete recommended)
python scripts/feishu_delete_risk_check.py `
  --token-type uat `
  --target "Example Doc::doccnxxxxxxxxxxxx"

# 7) one-command health check (pass/fail per step)
python scripts/feishu_skill_healthcheck.py `
  --file "config/feishu-auth.local.json" `
  --doc-id "doccnxxxxxxxxxxxx" `
  --refresh-uat `
  --fetch-tat
```

### Raw MCP Calls (Advanced)

Use [`scripts/lark_mcp_http.py`](scripts/lark_mcp_http.py) when you need full manual control over JSON-RPC methods and payloads.

## Agent Integration Patterns

### Pattern A: Native MCP Client (Preferred)

Use agent frameworks that support streamable HTTP MCP transports. Configure:
- URL: `https://mcp.feishu.cn/mcp`
- Headers: `Content-Type: application/json`, plus one of `X-Lark-MCP-UAT` or `X-Lark-MCP-TAT`
- Optional but recommended: `X-Lark-MCP-Allowed-Tools`

Apply platform-specific snippets from [`references/platform-recipes.md`](references/platform-recipes.md).

### Pattern B: Wrapper Tool (Fallback)

Expose `python scripts/lark_mcp_http.py ...` as an internal tool callable by the agent. Use this pattern when the platform does not support MCP transport configuration directly.

## Platform Notes

### OpenClaw

Prefer native MCP HTTP configuration if available in your OpenClaw runtime. If your current OpenClaw deployment lacks native remote-MCP config, register the wrapper script as an executable tool and pass token through environment variables.

### Claude Code and Codex

Use this folder as a reusable skill package. Keep token values out of source files and inject through environment variables (`FEISHU_MCP_UAT` or `FEISHU_MCP_TAT`) at runtime.

## Resources

- Tool and permission matrix: [`references/integration-checklist.md`](references/integration-checklist.md)
- UAT end-to-end guide: [`references/uat-first-runbook.md`](references/uat-first-runbook.md)
- Fixed command playbook for weaker agents: [`references/fixed-workflows.md`](references/fixed-workflows.md)
- Deletion safety policy: [`references/delete-policy.md`](references/delete-policy.md)
- Integration snippets for OpenClaw, Claude Code, Codex: [`references/platform-recipes.md`](references/platform-recipes.md)
- HTTP JSON-RPC caller: [`scripts/lark_mcp_http.py`](scripts/lark_mcp_http.py)
- Deterministic preset workflows: [`scripts/feishu_mcp_presets.py`](scripts/feishu_mcp_presets.py)
- Non-destructive deletion precheck: [`scripts/feishu_delete_risk_check.py`](scripts/feishu_delete_risk_check.py)
- OAuth helper for UAT: [`scripts/feishu_uat_oauth.py`](scripts/feishu_uat_oauth.py)
- OAuth callback listener: [`scripts/feishu_oauth_callback_server.py`](scripts/feishu_oauth_callback_server.py)
- JSON token store and rotation script: [`scripts/feishu_token_store.py`](scripts/feishu_token_store.py)

## Security Rules

1. Never commit UAT or TAT into repository files.
1. Prefer short-lived tokens and rotate them on schedule.
1. Scope `X-Lark-MCP-Allowed-Tools` per workflow step.
1. Log request ids and timestamps, but redact token values.
1. For deletion requests, warn risk first and recommend manual deletion in Feishu UI.

