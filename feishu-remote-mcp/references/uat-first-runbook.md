# UAT First Runbook

Use this when app creation and permission approval are already complete, and you want user-identity MCP calls first.

## 1) Confirm Admin Console Configuration

1. Ensure app status is enabled and visible to your test user.
1. Ensure OAuth redirect URI is configured in app security settings.
1. Ensure test user has app usage permission; otherwise OAuth token exchange may fail with code `20010`.
1. Ensure requested scopes include all MCP tools you plan to call.

## 2) Prepare Local Environment

```powershell
$env:FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxx"
```

Optional if you need `refresh_token`:
- Add `offline_access` in OAuth scope and app permission config.

## 3) Obtain Authorization Code

Generate browser URL:

```bash
python scripts/feishu_uat_oauth.py auth-url \
  --redirect-uri "http://localhost:8080/callback" \
  --scope "offline_access docs:document.comment:read docx:document:readonly"
```

Open `authorize_url` in browser, sign in, approve permissions, and capture `code` from callback query string.

Notes:
- Code is single-use.
- Code expires quickly (typically minutes).

Optional automatic callback capture:

```bash
python scripts/feishu_oauth_callback_server.py \
  --host localhost \
  --port 8080 \
  --path /callback \
  --state "state_from_auth_url"
```

Then open authorization URL. The listener prints JSON with `callback.code`.

## 4) Exchange Code for UAT

```bash
python scripts/feishu_uat_oauth.py exchange-code \
  --code "paste_code_here" \
  --redirect-uri "http://localhost:8080/callback" \
  --emit-env
```

Set runtime token:

```powershell
$env:FEISHU_MCP_UAT="u-gxxxxxxxxxxxxxxxx"
```

## 5) MCP Smoke Test with UAT

```bash
python scripts/feishu_mcp_presets.py \
  --token-type uat \
  smoke
```

Optional first business call:

```bash
python scripts/feishu_mcp_presets.py \
  --token-type uat \
  doc-roundtrip \
  --title "UAT First Runbook Test" \
  --markdown "Created from runbook flow."
```

## 6) Refresh Before Expiry

If refresh token is present:

```bash
python scripts/feishu_uat_oauth.py refresh-token \
  --refresh-token "paste_refresh_token_here" \
  --state-file "config/feishu-auth.local.json" \
  --emit-env
```

Store refreshed tokens in secret manager, not in repository files.

Weak-agent preferred command:

```bash
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  refresh-uat
```

This updates both `uat.access_token` and rotating `refresh.refresh_token` in the JSON file.

## 7) Common Failures to Check

1. `20003` or `20065`: authorization code invalid or already used.
1. `20004`: authorization code expired.
1. `20010`: user has no app usage permission.
1. `-32011`: MCP request missing `X-Lark-MCP-UAT`/`X-Lark-MCP-TAT`.
1. `result.isError=true`: tool-level failure in successful HTTP response.
