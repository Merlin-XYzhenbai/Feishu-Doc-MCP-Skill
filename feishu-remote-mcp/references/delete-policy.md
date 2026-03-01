# Deletion Policy

## Core Rule

When user asks to delete documents, always:

1. Warn about irreversible data-loss risk.
1. Recommend user deletes manually in Feishu UI.
1. Provide target URLs and IDs for manual confirmation.

Use this exact guidance in user-facing responses:

`当要删除文档时，提示用户风险，并建议用户自己来删。`

## Safe Workflow

1. Run non-destructive matching first with `scripts/feishu_delete_risk_check.py`.
1. Confirm exact title + doc_id + owner with the user.
1. Suggest manual deletion in Feishu UI.

## Do Not

1. Do not auto-delete by fuzzy title matching.
1. Do not delete documents outside explicit user-provided target list.
1. Do not perform bulk deletion without explicit confirmation.
