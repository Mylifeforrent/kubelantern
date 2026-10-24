#!/usr/bin/env python3
"""凭据/秘密泄漏扫描器 —— huntai-sre 安全护栏的规则核心。

三个入口共用本模块的规则，保持同一套判定标准：
  - .zcode/scripts/guard_bash.py   ZCode PreToolUse（Bash 命令）
  - .zcode/scripts/guard_write.py  ZCode PreToolUse（Write/Edit 写入内容）
  - .githooks/pre-commit           git 提交门禁（人工与 AI 提交的最后一道防线）

CLI 用法：
  python3 secret_scan.py text                  # 扫描 stdin 传入的文本
  python3 secret_scan.py file PATH [PATH...]   # 只扫描文件内容
  python3 secret_scan.py path PATH [PATH...]   # 路径规则 + 内容（git 门禁用）
      [--label NAME]                           # 报告中显示的名称（如仓库相对路径）

退出码：0 = 干净；1 = 发现问题；2 = 用法/运行错误。

规则为启发式：宁可少量误报，不可放过泄漏。误报时请改用明显占位符
（如 your-api-key、sk-xxxx）；规则调整必须由维护者人工修改本文件。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------- 规则定义


@dataclass(frozen=True)
class _Pattern:
    rule_id: str
    description: str
    rx: re.Pattern[str]
    value_group: int = 0  # 0 = 整个匹配作为“值”参与占位符判定


@dataclass(frozen=True)
class Finding:
    rule_id: str
    description: str
    line_no: int
    masked: str


_PATTERNS: list[_Pattern] = [
    _Pattern("AWS-AKID", "AWS Access Key ID",
             re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    _Pattern("AWS-SECRET", "AWS Secret Access Key（上下文匹配）",
             re.compile(r"(?i)aws[^:\n]{0,40}?(?:secret|sk)[^:\n]{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]"),
             1),
    _Pattern("PRIVATE-KEY", "私钥块（PEM / OPENSSH / PKCS#8 等）",
             re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY( BLOCK)?-----")),
    _Pattern("OPENAI", "OpenAI 风格密钥（sk-…，含 sk-proj-）",
             re.compile(r"\bsk-(?:proj-|svcacct-)?(?!ant-)[A-Za-z0-9_-]{20,}\b")),
    _Pattern("ANTHROPIC", "Anthropic 风格密钥（sk-ant-…）",
             re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    _Pattern("GITHUB", "GitHub Token（ghp_/gho_/ghu_/ghs_/ghr_/github_pat_）",
             re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    _Pattern("GITLAB", "GitLab PAT（glpat-…）",
             re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    _Pattern("SLACK", "Slack Token（xox…-）",
             re.compile(r"\bxox[baprsae]-[A-Za-z0-9-]{10,}\b")),
    _Pattern("GOOGLE", "Google API Key（AIza…）",
             re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    _Pattern("STRIPE", "Stripe 密钥（sk_test_/sk_live_/rk_…）",
             re.compile(r"\b[sr]k_(?:test|live)_[A-Za-z0-9]{16,}\b")),
    _Pattern("SENDGRID", "SendGrid API Key（SG.…）",
             re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b")),
    _Pattern("NPM-AUTHTOKEN", "npm authToken",
             re.compile(r"(?i)\b_auth?token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-./]{16,})"),
             1),
    _Pattern("JWT", "JWT（eyJ…）",
             re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b")),
    _Pattern("DB-URL", "连接串内嵌凭据（postgres/mysql/mongodb/redis/http…://user:pass@）",
             re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|rediss?|amqps?|mssql|https?)://"
                        r"(?:[^\s:@/'\"<>]{1,64})?:[^\s@/'\"<>]{4,}@[^\s'\"<>]+")),
    # 注意边界写法：DB_PASS、AWS_SECRET_KEY 这类下划线前缀变量名无法用 \b 命中，
    # 故用 (?:^|[^A-Za-z0-9]) 开头（允许 _、- 等分隔符，排除字母数字前后缀如 bypass），
    # 收尾 (?![A-Za-z0-9])（允许后面跟 _，排除 PASSWORD_HASH）。
    _Pattern("GENERIC-ASSIGN", "疑似密钥赋值（key/secret/token/password = 字面量）",
             re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:api[_-]?key|api[_-]?secret|secret(?:[_-]?key)?"
                        r"|access[_-]?key|access[_-]?token|auth(?:[_-]?token)?|client[_-]?secret"
                        r"|private[_-]?key|credential(?:s)?|passwd|password|pass|pwd|token)"
                        r"(?![A-Za-z0-9])['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})"),
             1),
    _Pattern("ZHIPU-HEX", "智谱/BigModel 风格密钥（上下文 + hex32 或 id.secret）",
             re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:zhipu|zai|bigmodel|glm)[A-Za-z0-9_.-]{0,32}['\"]?"
                        r"\s*[:=]\s*['\"]?([a-f0-9]{32}|[a-f0-9]{16}\.[A-Za-z0-9]{16})\b"),
             1),
]

# 禁止入库的文件路径规则（.env.example 显式放行）
_FORBIDDEN_PATHS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$", re.IGNORECASE),
     "本地环境变量文件（.env / .env.*，.env.example 除外）"),
    (re.compile(r"\.(pem|p12|pfx|jks|keystore|kdbx|key)$", re.IGNORECASE),
     "证书/私钥/密钥库文件"),
    (re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.[^/]*)?$", re.IGNORECASE),
     "SSH 私钥"),
    (re.compile(r"(^|/)credentials\.json$|(^|/)service[-_]?account[^/]*\.json$", re.IGNORECASE),
     "云厂商凭据 JSON"),
    (re.compile(r"(^|/)\.(netrc|htpasswd)$", re.IGNORECASE),
     "认证信息文件"),
    (re.compile(r"(^|/)secrets?\.(ya?ml|env|json|toml)$", re.IGNORECASE),
     "秘密清单文件"),
]

# 值为明显占位符/非秘密时不告警
_PLACEHOLDER_FULL_RE = re.compile(
    r"""^(?:
        \$\{?[A-Za-z_][A-Za-z0-9_]*\}?     # $VAR / ${VAR}
      | <[^<>]*>                           # <your-key>
      | \{\{?[^{}]*\}\}?                   # {VAR} / {{VAR}}
      | [xX*.\u2026]{3,}                   # xxxx / **** / ……
      | (?:true|false|yes|no|none|null|nil|undefined)
    )$""",
    re.VERBOSE,
)

_PLACEHOLDER_WORDS = (
    "your", "example", "sample", "placeholder", "dummy", "fake",
    "changeme", "change_me", "xxxx", "****", "....",
    "os.environ", "process.env", "getenv", "get_env", "dotenv",
    "<", ">", "${",
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "username", "user:", "admin", "root", "guest",
    "localhost", "/home", "/users/",
)

GUARD_TITLE = "[secret-guard] 检测到疑似凭据/秘密，已阻止。"

REMEDIATION = (
    "处理方式：\n"
    "  1. 真实凭据放到 .env（已被 .gitignore 排除）或密钥管理服务，代码中用环境变量引用；\n"
    "  2. 该密钥若曾泄漏过，立即到服务商后台吊销并轮换；\n"
    "  3. 若为文档示例等误报，请改用明显占位符（your-api-key、sk-xxxx）；规则调整由维护者人工修改 .zcode/scripts/secret_scan.py。"
)


# --------------------------------------------------------------- 判定逻辑


def _is_placeholder(value: str) -> bool:
    v = value.strip().strip("\"'`").rstrip(".,;:")
    if not v:
        return True
    if _PLACEHOLDER_FULL_RE.match(v):
        return True
    low = v.lower()
    if any(word in low for word in _PLACEHOLDER_WORDS):
        return True
    if re.search(r"(.)\1{3,}", v):  # 连续 4 个相同字符，多为掩码示例
        return True
    return False


def _mask(value: str) -> str:
    v = value.replace("\n", "\\n")
    head = v[:4] if len(v) >= 12 else v[:2]
    return f"{head}…(长度{len(v)})"


def scan_text(text: str) -> list[Finding]:
    """扫描文本，返回按行排序的发现列表（已去重、已过滤占位符）。"""
    findings: list[Finding] = []
    seen: set[tuple[str, int, int]] = set()
    for pat in _PATTERNS:
        for m in pat.rx.finditer(text):
            value = m.group(pat.value_group) if pat.value_group else m.group(0)
            if not value:
                continue
            value = value.strip().rstrip(".,;:")
            if len(value) < 6 or _is_placeholder(value):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            key = (pat.rule_id, line_no, m.start())
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(pat.rule_id, pat.description, line_no, _mask(value)))
    findings.sort(key=lambda f: (f.line_no, f.rule_id))
    return findings


def check_path(path_str: str) -> str | None:
    """路径命中禁止入库规则时返回原因描述，否则返回 None。"""
    p = path_str.strip().strip("\"'")
    if not p:
        return None
    for rx, reason in _FORBIDDEN_PATHS:
        if rx.search(p):
            return reason
    return None


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [Finding("READ-ERROR", f"文件无法读取：{exc}", 0, "")]
    return scan_text(text)


def format_findings(findings: list[Finding], label: str | None = None) -> str:
    where = label or ""
    lines = [f"  - {where}:{f.line_no} 规则 {f.rule_id}（{f.description}）片段 {f.masked}"
             if where else
             f"  - 第{f.line_no}行 规则 {f.rule_id}（{f.description}）片段 {f.masked}"
             for f in findings]
    return "\n".join(lines)


# --------------------------------------------------------------- CLI


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="凭据/秘密泄漏扫描器")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("text", help="扫描 stdin 文本")
    p_file = sub.add_parser("file", help="只扫描文件内容")
    p_file.add_argument("paths", nargs="+")
    p_path = sub.add_parser("path", help="路径规则 + 内容（git 门禁用）")
    p_path.add_argument("paths", nargs="+")
    p_path.add_argument("--label", default=None, help="报告中显示的名称")
    args = parser.parse_args(argv)

    if args.mode == "text":
        findings = scan_text(sys.stdin.read())
        if findings:
            print(GUARD_TITLE)
            print(format_findings(findings))
            return 1
        return 0

    bad = False
    for raw in args.paths:
        path = Path(raw)
        label = args.label if args.label else str(path)
        reason = check_path(str(path))
        if reason:
            bad = True
            print(f"[secret-guard] 禁止入库的文件：{label} —— {reason}")
        findings = scan_file(path)
        if findings:
            bad = True
            print(GUARD_TITLE)
            print(format_findings(findings, label))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
