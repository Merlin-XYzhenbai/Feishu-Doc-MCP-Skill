# Fixed Workflows for Weaker Agents

Use these deterministic commands when the calling agent is weak at planning multi-step MCP calls.

## 1) Prerequisites

Set one runtime token:

```powershell
$env:FEISHU_MCP_UAT="your_uat_here"
# or
$env:FEISHU_MCP_TAT="your_tat_here"
```

## 2) Minimum Health Check

```bash
python scripts/feishu_mcp_presets.py smoke --token-type uat
```

## 3) Tool Catalog Export

```bash
python scripts/feishu_mcp_presets.py catalog --token-type uat
```

This prints tool names plus required fields from `inputSchema`.

## 4) Document Workflows

Create:

```bash
python scripts/feishu_mcp_presets.py doc-create \
  --token-type uat \
  --title "Agent Fixed Flow Test" \
  --markdown "Created by fixed workflow."
```

Read:

```bash
python scripts/feishu_mcp_presets.py doc-read \
  --token-type uat \
  --doc-id "doccnxxxxxxxxxxxx"
```

Comment:

```bash
python scripts/feishu_mcp_presets.py doc-comment \
  --token-type uat \
  --doc-id "doccnxxxxxxxxxxxx" \
  --comment "Automated review note."
```

Read comments:

```bash
python scripts/feishu_mcp_presets.py doc-comments \
  --token-type uat \
  --doc-id "doccnxxxxxxxxxxxx" \
  --comment-type all
```

Notes:
- `doc-comment` now auto-builds `add-comments` payload as `elements=[{"type":"text","text":"..."}]`.
- If you need mention or link, pass explicit elements with `--set elements=json:[...]`.
- `add-comments` does not support markdown/image/file/emoji as comment elements.
- `doc-comments` returns `comments_summary` and a structured `diagnostic` when permission is missing.

Roundtrip (create + read + optional comment):

```bash
python scripts/feishu_mcp_presets.py doc-roundtrip \
  --token-type uat \
  --title "Roundtrip Test" \
  --markdown "Created by doc-roundtrip." \
  --comment "Roundtrip comment"
```

## 5) User Workflows

Current user:

```bash
python scripts/feishu_mcp_presets.py user-self --token-type uat
```

Search user:

```bash
python scripts/feishu_mcp_presets.py user-search \
  --token-type uat \
  --query "alice"
```

## 6) Generic Tool Call with Explicit Args

```bash
python scripts/feishu_mcp_presets.py tool-call \
  --token-type uat \
  --tool fetch-doc \
  --doc-id "doccnxxxxxxxxxxxx"
```

Explicit args:

```bash
python scripts/feishu_mcp_presets.py tool-call \
  --token-type uat \
  --tool fetch-doc \
  --set docID=doccnxxxxxxxxxxxx
```

## 7) Deletion Risk Check (Non-Destructive)

When user asks to delete docs, do not delete first. Run risk check and recommend manual deletion.

```bash
python scripts/feishu_delete_risk_check.py \
  --token-type uat \
  --target "UAT MCP Test 2026-02-28 10:21:51 UTC::P1TbdyYDjoxZjCxAL3CchFfWnUb" \
  --target "UAT Preset Skill Verification::Yr2Fdm36vojsnAx6OH9cvEbGnac"
```

Policy:
- 当要删除文档时，先提示风险，并建议用户自己在飞书界面删除。
- This policy is implemented by `scripts/feishu_delete_risk_check.py` as a non-destructive precheck.
- Only proceed after user re-confirms exact `title + doc_id`.

## 8) Guardrails

1. Keep allowlist minimal when possible.
1. Prefer UAT for user-owned doc operations.
1. Do not depend on stable output schema; parse only needed fields.
1. On `result.isError=true`, inspect `result.content[].text` and retry with explicit `--set`.

## 9) Token Rotation for Weaker Agents

Initialize JSON store once:

```bash
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  init \
  --app-id "cli_xxx" \
  --app-secret "xxx" \
  --redirect-uri "http://localhost:8080/callback"
```

After OAuth callback code:

```bash
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  exchange-code \
  --code "paste_code_here"
```

Refresh UAT (rotates refresh_token):

```bash
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  refresh-uat
```

Fetch TAT:

```bash
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  fetch-tat
```

## 10) get-comments Scope Repair (UAT)

When `doc-comments` returns `diagnostic.category=missing_user_scope`, rotate to a newly authorized UAT that includes `contact:contact.base:readonly`.

```bash
# 1) Generate OAuth URL with required scope
python scripts/feishu_uat_oauth.py auth-url \
  --redirect-uri "http://localhost:8080/callback" \
  --scope "offline_access docs:document.comment:read contact:contact.base:readonly"

# 2) Browser authorize -> copy callback code
# 3) Exchange code and persist new UAT/refresh token
python scripts/feishu_token_store.py \
  --file "config/feishu-auth.local.json" \
  exchange-code \
  --code "paste_code_here"

# 4) Retry comment read
python scripts/feishu_mcp_presets.py doc-comments \
  --token-type uat \
  --doc-id "doccnxxxxxxxxxxxx" \
  --comment-type all
```

## 11) One-Command Health Check

Use this non-destructive check for weak agents. It returns per-step `pass/fail/skipped` plus reason.

```bash
python scripts/feishu_skill_healthcheck.py \
  --file "config/feishu-auth.local.json" \
  --doc-id "doccnxxxxxxxxxxxx" \
  --refresh-uat \
  --fetch-tat
```

Output notes:
- `ok=true` means no failed steps.
- `summary` includes pass/fail/skipped counts.
- On failure, read each step `reason` and `details` for direct troubleshooting hints.
