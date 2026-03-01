#!/usr/bin/env python3
"""One-command health check for feishu-remote-mcp skill."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class StepResult:
    name: str
    status: str
    reason: str
    exit_code: int | None = None
    command: list[str] | None = None
    details: dict[str, Any] | None = None


SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "tenant_access_token",
    "app_secret",
    "token",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config json must be an object")
    return data


def parse_json_output(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def mask_secret(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) <= 12:
        return "***"
    return value[:6] + "..." + value[-6:]


def sanitize_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for key, value in obj.items():
            if key in SECRET_KEYS:
                sanitized[key] = mask_secret(value)
            else:
                sanitized[key] = sanitize_obj(value)
        return sanitized
    if isinstance(obj, list):
        return [sanitize_obj(item) for item in obj]
    return obj


def redact_command(cmd: list[str] | None) -> list[str] | None:
    if cmd is None:
        return None
    redacted: list[str] = []
    i = 0
    while i < len(cmd):
        token = cmd[i]
        redacted.append(token)
        if token == "--token" and i + 1 < len(cmd):
            redacted.append("***REDACTED***")
            i += 2
            continue
        i += 1
    return redacted


def step_to_dict(step: StepResult) -> dict[str, Any]:
    return {
        "name": step.name,
        "status": step.status,
        "reason": step.reason,
        "exit_code": step.exit_code,
        "command": redact_command(step.command),
        "details": sanitize_obj(step.details) if step.details is not None else None,
    }


def print_json_safe(payload: dict[str, Any], compact: bool) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=None if compact else 2)
    try:
        print(text)
        return
    except UnicodeEncodeError:
        pass
    print(json.dumps(payload, ensure_ascii=True, indent=None if compact else 2))


def extract_token(store: dict[str, Any], token_type: str) -> str | None:
    node = store.get(token_type)
    if not isinstance(node, dict):
        return None
    token = node.get("access_token")
    return token if isinstance(token, str) and token else None


def summarize_doc_comments(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        return "no result object"
    summary = result.get("comments_summary")
    if not isinstance(summary, dict):
        return "no comments_summary"
    count = summary.get("comment_count")
    whole = summary.get("whole_count")
    segment = summary.get("segment_count")
    return f"count={count}, whole={whole}, segment={segment}"


def diagnose_failure(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        return "unknown error"
    diagnostic = result.get("diagnostic")
    if isinstance(diagnostic, dict):
        category = diagnostic.get("category")
        message = diagnostic.get("message")
        return f"diagnostic={category}, message={message}"
    nested = result.get("result")
    if isinstance(nested, dict):
        tool_call = nested.get("tool_call")
        if isinstance(tool_call, dict):
            return f"tool_call_ok={tool_call.get('ok')}, is_tool_error={tool_call.get('is_tool_error')}"
    return "command failed without structured diagnostic"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="One-command health check for feishu-remote-mcp skill.")
    parser.add_argument("--file", default="config/feishu-auth.local.json", help="Token store JSON path.")
    parser.add_argument("--doc-id", help="Optional doc id for comment/read checks.")
    parser.add_argument("--refresh-uat", action="store_true", help="Refresh UAT before checks.")
    parser.add_argument("--fetch-tat", action="store_true", help="Fetch TAT before checks.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    config_path = Path(args.file)
    if not config_path.is_absolute():
        config_path = (root / config_path).resolve()

    steps: list[StepResult] = []
    output: dict[str, Any] = {
        "timestamp_utc": utc_now(),
        "config_file": str(config_path),
        "root": str(root),
    }

    if not config_path.exists():
        steps.append(
            StepResult(
                name="config_exists",
                status="fail",
                reason=f"config file not found: {config_path}",
            )
        )
        output["steps"] = [step_to_dict(step) for step in steps]
        output["ok"] = False
        print_json_safe(output, args.compact)
        return 1

    try:
        store = read_json_file(config_path)
    except Exception as exc:
        steps.append(
            StepResult(
                name="config_parse",
                status="fail",
                reason=f"failed to parse config: {exc}",
            )
        )
        output["steps"] = [step_to_dict(step) for step in steps]
        output["ok"] = False
        print_json_safe(output, args.compact)
        return 1

    steps.append(StepResult(name="config_parse", status="pass", reason="config parsed"))

    if args.refresh_uat:
        cmd = [
            args.python,
            str(scripts / "feishu_token_store.py"),
            "--file",
            str(config_path),
            "refresh-uat",
        ]
        code, stdout, stderr = run_cmd(cmd, root)
        details = parse_json_output(stdout) or {"stdout_tail": stdout[-800:]}
        if code == 0:
            steps.append(
                StepResult(
                    name="refresh_uat",
                    status="pass",
                    reason="refresh-uat succeeded",
                    exit_code=code,
                    command=cmd,
                    details=details,
                )
            )
            store = read_json_file(config_path)
        else:
            steps.append(
                StepResult(
                    name="refresh_uat",
                    status="fail",
                    reason=f"refresh-uat failed: {stderr.strip()[:240]}",
                    exit_code=code,
                    command=cmd,
                    details=details,
                )
            )

    if args.fetch_tat:
        cmd = [
            args.python,
            str(scripts / "feishu_token_store.py"),
            "--file",
            str(config_path),
            "fetch-tat",
        ]
        code, stdout, stderr = run_cmd(cmd, root)
        details = parse_json_output(stdout) or {"stdout_tail": stdout[-800:]}
        if code == 0:
            steps.append(
                StepResult(
                    name="fetch_tat",
                    status="pass",
                    reason="fetch-tat succeeded",
                    exit_code=code,
                    command=cmd,
                    details=details,
                )
            )
            store = read_json_file(config_path)
        else:
            steps.append(
                StepResult(
                    name="fetch_tat",
                    status="fail",
                    reason=f"fetch-tat failed: {stderr.strip()[:240]}",
                    exit_code=code,
                    command=cmd,
                    details=details,
                )
            )

    uat = extract_token(store, "uat")
    tat = extract_token(store, "tat")

    if uat:
        steps.append(StepResult(name="uat_token_present", status="pass", reason="uat token found"))
    else:
        steps.append(StepResult(name="uat_token_present", status="fail", reason="uat token missing"))

    if tat:
        steps.append(StepResult(name="tat_token_present", status="pass", reason="tat token found"))
    else:
        steps.append(StepResult(name="tat_token_present", status="skipped", reason="tat token missing"))

    if uat:
        cmd = [
            args.python,
            str(scripts / "feishu_mcp_presets.py"),
            "--token-type",
            "uat",
            "--token",
            uat,
            "--compact",
            "smoke",
        ]
        code, stdout, stderr = run_cmd(cmd, root)
        payload = parse_json_output(stdout) or {}
        if code == 0:
            reason = "uat smoke ok"
            steps.append(
                StepResult(
                    name="uat_smoke",
                    status="pass",
                    reason=reason,
                    exit_code=code,
                    command=cmd,
                    details=payload,
                )
            )
        else:
            steps.append(
                StepResult(
                    name="uat_smoke",
                    status="fail",
                    reason=f"uat smoke failed: {stderr.strip()[:240]}",
                    exit_code=code,
                    command=cmd,
                    details=payload,
                )
            )

    if tat:
        cmd = [
            args.python,
            str(scripts / "feishu_mcp_presets.py"),
            "--token-type",
            "tat",
            "--token",
            tat,
            "--compact",
            "smoke",
        ]
        code, stdout, stderr = run_cmd(cmd, root)
        payload = parse_json_output(stdout) or {}
        if code == 0:
            steps.append(
                StepResult(
                    name="tat_smoke",
                    status="pass",
                    reason="tat smoke ok",
                    exit_code=code,
                    command=cmd,
                    details=payload,
                )
            )
        else:
            steps.append(
                StepResult(
                    name="tat_smoke",
                    status="fail",
                    reason=f"tat smoke failed: {stderr.strip()[:240]}",
                    exit_code=code,
                    command=cmd,
                    details=payload,
                )
            )

    if args.doc_id:
        if uat:
            cmd = [
                args.python,
                str(scripts / "feishu_mcp_presets.py"),
                "--token-type",
                "uat",
                "--token",
                uat,
                "--compact",
                "doc-comments",
                "--doc-id",
                args.doc_id,
                "--comment-type",
                "all",
            ]
            code, stdout, stderr = run_cmd(cmd, root)
            payload = parse_json_output(stdout) or {}
            if code == 0:
                reason = f"uat doc-comments ok ({summarize_doc_comments(payload)})"
                steps.append(
                    StepResult(
                        name="uat_doc_comments",
                        status="pass",
                        reason=reason,
                        exit_code=code,
                        command=cmd,
                        details=payload,
                    )
                )
            else:
                reason = diagnose_failure(payload)
                if stderr.strip():
                    reason = f"{reason}; stderr={stderr.strip()[:180]}"
                steps.append(
                    StepResult(
                        name="uat_doc_comments",
                        status="fail",
                        reason=reason,
                        exit_code=code,
                        command=cmd,
                        details=payload,
                    )
                )

        if tat:
            cmd = [
                args.python,
                str(scripts / "feishu_mcp_presets.py"),
                "--token-type",
                "tat",
                "--token",
                tat,
                "--compact",
                "doc-comments",
                "--doc-id",
                args.doc_id,
                "--comment-type",
                "all",
            ]
            code, stdout, stderr = run_cmd(cmd, root)
            payload = parse_json_output(stdout) or {}
            if code == 0:
                reason = f"tat doc-comments ok ({summarize_doc_comments(payload)})"
                steps.append(
                    StepResult(
                        name="tat_doc_comments",
                        status="pass",
                        reason=reason,
                        exit_code=code,
                        command=cmd,
                        details=payload,
                    )
                )
            else:
                reason = diagnose_failure(payload)
                if stderr.strip():
                    reason = f"{reason}; stderr={stderr.strip()[:180]}"
                steps.append(
                    StepResult(
                        name="tat_doc_comments",
                        status="fail",
                        reason=reason,
                        exit_code=code,
                        command=cmd,
                        details=payload,
                    )
                )
    else:
        steps.append(
            StepResult(
                name="doc_checks",
                status="skipped",
                reason="--doc-id not provided",
            )
        )

    pass_count = sum(1 for step in steps if step.status == "pass")
    fail_count = sum(1 for step in steps if step.status == "fail")
    skipped_count = sum(1 for step in steps if step.status == "skipped")

    output["steps"] = [step_to_dict(step) for step in steps]
    output["summary"] = {
        "pass": pass_count,
        "fail": fail_count,
        "skipped": skipped_count,
        "total": len(steps),
    }
    output["ok"] = fail_count == 0

    print_json_safe(output, args.compact)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
