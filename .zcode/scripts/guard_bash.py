#!/usr/bin/env python3
"""ZCode PreToolUse hook —— Bash 命令护栏。

拦截范围：
  1. 命令文本中出现疑似凭据（secret_scan 规则）；
  2. git 操作明确指向禁止入库的文件（.env、*.pem 等）；
  3. git commit --no-verify（项目安全红线：绕过凭据门禁）。

输入：stdin 的 hook 事件 JSON（取 tool_input.command）。
输出：0 放行；2 拦截（stderr 给出原因）。
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secret_scan import GUARD_TITLE, REMEDIATION, check_path, format_findings, scan_text


def _block(lines: list[str]) -> int:
    print(GUARD_TITLE, file=sys.stderr)
    for line in lines:
        print(line, file=sys.stderr)
    print(REMEDIATION, file=sys.stderr)
    return 2


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # 输入异常时放行，git 门禁仍是最后一道防线

    command = str((data.get("tool_input") or {}).get("command") or "")
    if not command.strip():
        return 0

    findings = scan_text(command)
    if findings:
        return _block(["原因：命令中包含疑似凭据。", format_findings(findings)])

    if re.search(r"\bgit\b", command) and "--no-verify" in command:
        return _block(["原因：项目安全红线禁止 git commit --no-verify（会绕过凭据检查）。"])

    if re.search(r"\bgit\b[^;&|]{0,120}?\b(add|stage|commit|rm|mv)\b", command):
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        bad: list[tuple[str, str]] = []
        for tok in tokens:
            if tok == "git" or tok.startswith("-"):
                continue
            reason = check_path(tok)
            if reason:
                bad.append((tok, reason))
        if bad:
            lines = ["原因：git 操作的目标中包含禁止入库的文件："]
            lines += [f"  - {p} —— {why}" for p, why in bad]
            lines.append("这些文件只能保留在本地，并确认已被 .gitignore 排除。")
            return _block(lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
