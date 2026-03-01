# Feishu Remote MCP Skill Quickstart

This repository packages Feishu Remote MCP integration into a reusable skill and provides fixed scripts that weaker agents can run reliably.

## Author

- Publisher: Merlin
- Contact: merlin_working@outlook.com

## 1. Repository Layout

- `feishu-remote-mcp/SKILL.md`: Skill entry and operating rules.
- `feishu-remote-mcp/scripts/`: Automation scripts (OAuth, token rotation, MCP presets, risk checks, health check).
- `feishu-remote-mcp/references/`: Integration guides and fixed workflow docs.
- `feishu-remote-mcp/config/`: Local credential store (git-ignored).

## 2. Prerequisites

Before running scripts, complete setup in Feishu Open Platform:

- Create a custom app.
- Configure redirect URLs:
  - `http://localhost:8080/callback`
  - `http://127.0.0.1:8080/callback`
- Grant required scopes (see section 11 for baseline scope config).

## 3. Initialize Local Credential Store

```powershell
python feishu-remote-mcp/scripts/feishu_token_store.py `
  --file "feishu-remote-mcp/config/feishu-auth.local.json" `
  init `
  --app-id "YOUR_APP_ID" `
  --app-secret "YOUR_APP_SECRET" `
  --redirect-uri "http://localhost:8080/callback"
```

## 4. Get UAT (User Access Token)

Generate authorize URL:

```powershell
python feishu-remote-mcp/scripts/feishu_uat_oauth.py `
  auth-url `
  --client-id "YOUR_APP_ID" `
  --redirect-uri "http://localhost:8080/callback" `
  --scope "offline_access docx:document:create docx:document:write_only docx:document:readonly docs:document.comment:create docs:document.comment:read search:docs:read wiki:wiki:readonly wiki:node:read wiki:node:create contact:contact.base:readonly"
```

After browser consent, exchange callback `code`:

```powershell
python feishu-remote-mcp/scripts/feishu_token_store.py `
  --file "feishu-remote-mcp/config/feishu-auth.local.json" `
  exchange-code `
  --code "CODE_FROM_CALLBACK"
```

Refresh UAT later:

```powershell
python feishu-remote-mcp/scripts/feishu_token_store.py `
  --file "feishu-remote-mcp/config/feishu-auth.local.json" `
  refresh-uat
```

## 5. Get TAT (Tenant Access Token)

```powershell
python feishu-remote-mcp/scripts/feishu_token_store.py `
  --file "feishu-remote-mcp/config/feishu-auth.local.json" `
  fetch-tat
```

## 6. Fixed Flows for Weaker Agents

Load UAT from store:

```powershell
$cfg = Get-Content -Path "feishu-remote-mcp/config/feishu-auth.local.json" -Raw | ConvertFrom-Json
$env:FEISHU_MCP_UAT = $cfg.uat.access_token
```

Smoke test:

```powershell
python feishu-remote-mcp/scripts/feishu_mcp_presets.py --token-type uat smoke
```

Create/read/comment roundtrip:

```powershell
python feishu-remote-mcp/scripts/feishu_mcp_presets.py `
  --token-type uat `
  doc-roundtrip `
  --title "UAT Comment Verification" `
  --markdown "Created by quickstart." `
  --comment "Comment from preset workflow."
```

Read comments (whole + segment):

```powershell
python feishu-remote-mcp/scripts/feishu_mcp_presets.py `
  --token-type uat `
  doc-comments `
  --doc-id "DOC_ID" `
  --comment-type all
```

Notes:

- `add-comments` supports text, mention, and link elements.
- `add-comments` does not support markdown/image/file/emoji elements.
- If `doc-comments` returns `diagnostic.category=missing_user_scope`, re-authorize UAT with `contact:contact.base:readonly`.

## 7. Deletion Risk Policy

For delete requests, always warn users and recommend manual deletion in Feishu UI first.

Use non-destructive risk precheck:

```powershell
python feishu-remote-mcp/scripts/feishu_delete_risk_check.py `
  --token-type uat `
  --target "Document Title::DOC_ID"
```

Only proceed after user reconfirms exact `title + doc_id`.

## 8. Security Rules

- Keep `feishu-remote-mcp/config/feishu-auth.local.json` local only (already git-ignored).
- Never commit `App Secret`, `UAT`, `TAT`, or `refresh_token`.
- Use secret manager injection in production.

## 9. UAT Scope Expansion Rule

- When you add new permissions in Feishu console, existing `refresh_token` can renew tokens but cannot add new scopes.
- To obtain newly added scopes, you must re-run browser authorization and then run `exchange-code`.
- After that, continue rotation with `refresh-uat`.

## 10. One-Command Health Check (Recommended for Weaker Agents)

Script: `feishu-remote-mcp/scripts/feishu_skill_healthcheck.py`  
Purpose: run key checks and return per-step `pass/fail/skipped + reason`.

```powershell
python feishu-remote-mcp/scripts/feishu_skill_healthcheck.py `
  --file "feishu-remote-mcp/config/feishu-auth.local.json" `
  --doc-id "DOC_ID" `
  --refresh-uat `
  --fetch-tat
```

Output:

- `ok=true` means no failed steps.
- `summary` includes pass/fail/skipped counts.
- Checks are non-destructive by default.

## 11. Feishu Open Platform Scope Baseline

Use this scope baseline when configuring the app for this skill:

```json
{
  "scopes": {
    "tenant": [
      "board:whiteboard:node:create",
      "board:whiteboard:node:read",
      "contact:contact.base:readonly",
      "contact:user.base:readonly",
      "docs:document.comment:create",
      "docs:document.comment:read",
      "docs:document.media:download",
      "docs:document.media:upload",
      "docx:document:create",
      "docx:document:readonly",
      "docx:document:write_only",
      "wiki:node:create",
      "wiki:node:read",
      "wiki:wiki:readonly"
    ],
    "user": [
      "drive:drive",
      "drive:drive.metadata:readonly",
      "drive:drive.search:readonly",
      "drive:drive:readonly",
      "drive:drive:version",
      "drive:drive:version:readonly",
      "board:whiteboard:node:create",
      "board:whiteboard:node:read",
      "contact:contact.base:readonly",
      "contact:user.base:readonly",
      "contact:user:search",
      "docs:doc",
      "docs:doc:readonly",
      "docs:document.comment:create",
      "docs:document.comment:read",
      "docs:document.comment:update",
      "docs:document.comment:write_only",
      "docs:document.content:read",
      "docs:document.media:download",
      "docs:document.media:upload",
      "docs:document.subscription",
      "docs:document.subscription:read",
      "docs:document:copy",
      "docs:document:export",
      "docs:document:import",
      "docs:event.document_deleted:read",
      "docs:event.document_edited:read",
      "docs:event.document_opened:read",
      "docs:event:subscribe",
      "docs:permission.member:create",
      "docs:permission.member:delete",
      "docs:permission.member:readonly",
      "docs:permission.member:retrieve",
      "docs:permission.member:transfer",
      "docs:permission.member:update",
      "docs:permission.setting",
      "docs:permission.setting:read",
      "docs:permission.setting:readonly",
      "docs:permission.setting:write_only",
      "document_ai:health_certificate:recognize",
      "document_ai:vehicle_invoice:recognize",
      "docx:document",
      "docx:document.block:convert",
      "docx:document:create",
      "docx:document:readonly",
      "docx:document:write_only",
      "offline_access",
      "search:docs:read",
      "space:document.event:read",
      "space:document:delete",
      "space:document:move",
      "space:document:retrieve",
      "space:document:shortcut",
      "wiki:node:create",
      "wiki:node:read",
      "wiki:wiki:readonly"
    ]
  }
}
```
