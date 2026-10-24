#!/usr/bin/env python3
"""ZCode PreToolUse hook —— Write/Edit 写入内容护栏。

拦截范围：
  1. 写入/编辑安全护栏自身文件（config.json、scripts、.githooks）——护栏只允许人工修改；
  2. 向普通文件写入疑似凭据。

放行约定：向 .env、*.pem 等本地秘密文件写入是合法用途（它们被 .gitignore
排除，入库防线在 pre-commit），因此这类路径不做内容扫描。

输入：stdin 的 hook 事件 JSON（取 tool_input 的 file_path/content/new_string/edits）。
输出：0 放行；2 拦截（stderr 给出原因）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secret_scan import GUARD_TITLE, REMEDIATION, check_path, format_findings, scan_text

# 护栏自身文件：只允许维护者人工修改，AI（含子代理）的写入一律拦截
_PROTECTED_RES = [
    r"(^|/)\.zcode/config\.json$",
    r"(^|/)\.zcode/scripts/",
    r"(^|/)\.githooks/",
]


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

    tool_input = data.get("tool_input") or {}
    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")

    for rx in _PROTECTED_RES:
        if re.search(rx, path):
            print("[secret-guard] 目标文件属于安全护栏，已阻止 AI 修改。", file=sys.stderr)
            print(f"文件：{path}", file=sys.stderr)
            print("护栏规则只能由维护者人工编辑，改完后重启会话生效。", file=sys.stderr)
            return 2

    # 本地秘密文件（.env、*.pem 等）允许写入，入库由 pre-commit 把关
    if path and check_path(path):
        return 0

    texts: list[str] = []
    if tool_input.get("content") is not None:
        texts.append(str(tool_input["content"]))
    if tool_input.get("new_string"):
        texts.append(str(tool_input["new_string"]))
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and edit.get("new_string"):
            texts.append(str(edit["new_string"]))
    if not texts:
        return 0

    findings: list = []
    for text in texts:
        findings.extend(scan_text(text))
    if findings:
        lines = [f"原因：写入 {path or '（未知文件）'} 的内容中包含疑似凭据。",
                 format_findings(findings)]
        return _block(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
