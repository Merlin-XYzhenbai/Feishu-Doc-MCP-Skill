# Feishu Remote MCP Integration Checklist

## 1) Tenant Preparation

1. Create a self-built app in Feishu Open Platform.
1. Enable required API permissions for every MCP tool you plan to call.
1. Choose identity mode:
- `UAT` for user-identity calls.
- `TAT` for app-identity server calls.
1. Configure app availability so test users can use the app.
1. Configure OAuth redirect URI if using UAT authorization code flow.

## 2) Required Request Contract

- Endpoint: `POST https://mcp.feishu.cn/mcp`
- Headers:
- `Content-Type: application/json`
- `X-Lark-MCP-UAT` or `X-Lark-MCP-TAT`
- `X-Lark-MCP-Allowed-Tools` (strongly recommended; missing header may prevent tool discovery and calls)
- Body format: JSON-RPC 2.0
- Core fields: `jsonrpc: "2.0"`, `id`, `method`, optional `params`

## 3) Recommended Smoke Test

1. `initialize`
1. `tools/list`
1. `tools/call` for one read-only tool (for example `fetch-doc`)

Use the same token and allowlist in all three calls.

Preset command alternative:

```bash
python scripts/feishu_mcp_presets.py --token-type uat smoke
```

For UAT, ensure token comes from OAuth exchange:
- `POST https://open.feishu.cn/open-apis/authen/v2/oauth/token`
- `grant_type=authorization_code`

## 4) Tool and Permission Reference

This list tracks the currently documented scope from Feishu docs provided in the project context.

Tool | UAT/TAT | Key Permissions
---|---|---
`search-user` | UAT | `contact:user:search`
`get-user` | UAT/TAT | `contact:contact.base:readonly`, `contact:user.base:readonly`
`fetch-file` | UAT/TAT | `docs:document.media:download`, `board:whiteboard:node:read`
`search-doc` | UAT | `search:docs:read`, `wiki:wiki:readonly`
`create-doc` | UAT/TAT | `docx:document:create`, `docx:document:write_only`, `docx:document:readonly`, `wiki:node:read`, `wiki:node:create`, `docs:document.media:upload`, `board:whiteboard:node:create`
`fetch-doc` | UAT/TAT | `docx:document:readonly`, `task:task:read`, `im:chat:read`
`update-doc` | UAT/TAT | Same as `create-doc`
`list-docs` | UAT/TAT | `wiki:wiki:readonly`
`get-comments` | UAT/TAT | `docs:document.comment:read`, `contact:contact.base:readonly`
`add-comments` | UAT/TAT | `docs:document.comment:create`

## 5) Error Handling Contract

Handle both layers:

1. Transport / protocol errors
- Non-2xx HTTP status
- Top-level JSON-RPC `error` object

1. Tool execution errors in success HTTP responses
- `result.isError == true`
- Error payload usually inside `result.content[].text`

## 6) Compatibility Guardrails

1. Do not hardcode tool input/output schema assumptions.
1. Parse only needed fields and keep fallback handling.
1. Keep request `id` values and logs for incident triage.
1. For deletion requests, warn risk and recommend manual deletion in Feishu UI first.
