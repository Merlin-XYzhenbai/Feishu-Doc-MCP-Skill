# Platform Recipes: OpenClaw, Claude Code, Codex

## 1) Environment Variables

Set exactly one token type per session:

```powershell
$env:FEISHU_MCP_TAT="t-gxxxxxxxxxxxxxxxxxxxxx"
# or
$env:FEISHU_MCP_UAT="u-gxxxxxxxxxxxxxxxxxxxxx"
```

For UAT OAuth exchange:

```powershell
$env:FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxx"
```

Optional persisted token store:

```bash
python scripts/feishu_token_store.py --file "config/feishu-auth.local.json" show
```

## 2) UAT First Bootstrap (Recommended)

1. Generate authorize URL.
1. Complete browser consent and obtain code.
1. Exchange code to `user_access_token`.
1. Set `FEISHU_MCP_UAT`.
1. Run `initialize` and `tools/list`.

Commands:

```bash
python scripts/feishu_uat_oauth.py auth-url \
  --redirect-uri "http://localhost:8080/callback" \
  --scope "offline_access docx:document:readonly"

python scripts/feishu_uat_oauth.py exchange-code \
  --code "paste_code_here" \
  --redirect-uri "http://localhost:8080/callback" \
  --state-file "config/feishu-auth.local.json" \
  --emit-env
```

## 3) Native MCP Client Recipe (Preferred)

Use this when your agent runtime supports HTTP MCP transports.

Required config values:
- URL: `https://mcp.feishu.cn/mcp`
- Method: `POST`
- Headers:
- `Content-Type: application/json`
- `X-Lark-MCP-TAT` or `X-Lark-MCP-UAT`
- `X-Lark-MCP-Allowed-Tools` with a minimal allowlist

Example allowlist:

```text
fetch-doc,update-doc,search-user
```

## 4) Wrapper Script Recipe (Portable)

Use this for any runtime (including OpenClaw or Codex workflows) when native MCP config is unavailable.

```bash
python scripts/feishu_mcp_presets.py \
  --token-type uat \
  smoke
```

Deterministic document workflow:

```bash
python scripts/feishu_mcp_presets.py \
  --token-type uat \
  doc-roundtrip \
  --title "Preset Roundtrip" \
  --markdown "Created by preset workflow." \
  --comment "Preset comment"
```

Raw wrapper (advanced):

```bash
python scripts/lark_mcp_http.py \
  --token-type tat \
  --allowed-tools "fetch-doc,update-doc" \
  --method tools/call \
  --tool-name fetch-doc \
  --arguments "{\"docID\":\"doccnxxxxxxxxxxxx\"}"
```

Wrap this command as an internal tool in your agent framework.

## 5) OpenClaw Notes

1. Prefer native remote MCP integration if your deployed OpenClaw version supports streamable HTTP MCP.
1. Fall back to the wrapper script when direct MCP client configuration is not exposed.
1. Store tokens in runtime secret management and inject as environment variables.

## 6) Claude Code / Codex Notes

1. Keep this skill folder available in your workspace or Codex skill path.
1. Invoke `$feishu-remote-mcp` when tasks involve Feishu cloud docs or Feishu user/doc/comment tools.
1. Call the wrapper script from terminal tools if no direct MCP transport wiring is configured.
1. For delete-doc requests, show risk warning and suggest user deletes manually in Feishu UI.

## 7) Minimal Agent-Side Pseudocode

```python
def call_feishu_mcp(method, params=None):
    headers = {
        "Content-Type": "application/json",
        "X-Lark-MCP-TAT": os.environ["FEISHU_MCP_TAT"],
        "X-Lark-MCP-Allowed-Tools": "fetch-doc,update-doc",
    }
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return http_post_json("https://mcp.feishu.cn/mcp", headers, body)
```

For tool calls:

```python
call_feishu_mcp("tools/call", {
    "name": "fetch-doc",
    "arguments": {"docID": "doccnxxxxxxxxxxxx"}
})
```
