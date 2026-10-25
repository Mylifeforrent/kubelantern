"""出站脱敏与本地还原（BR-01）。

- 出域文本仅含占位符 K8S_MASK_NNNN；原值信封加密落 ai_mask_mappings.encrypted_original（仅本地）。
- kind：namespace / pod / ip / credential。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|secret)\b['\"\s:=]+([^\s'\",;]{4,})"
)


@dataclass
class MaskMapping:
    placeholder: str
    kind: str
    original: str


@dataclass
class SanitizeResult:
    text: str
    mappings: list[MaskMapping] = field(default_factory=list)


def sanitize(text: str, *, known_terms: dict[str, str] | None = None) -> SanitizeResult:
    """known_terms: {原值: kind}（如 namespace/pod 名），优先掩蔽后叠加正则。"""
    mappings: list[MaskMapping] = []
    replaced: dict[str, str] = {}

    def _mask(value: str, kind: str) -> str:
        if value in replaced:
            return replaced[value]
        placeholder = f"K8S_MASK_{len(mappings):04d}"
        mappings.append(MaskMapping(placeholder=placeholder, kind=kind, original=value))
        replaced[value] = placeholder
        return placeholder

    for original, kind in (known_terms or {}).items():
        if original and original in text:
            text = text.replace(original, _mask(original, kind))

    def _cred_repl(match: re.Match) -> str:
        return f"{match.group(1)}={_mask(match.group(2), 'credential')}"

    text = _CREDENTIAL_PATTERN.sub(_cred_repl, text)
    text = _IP_PATTERN.sub(lambda m: _mask(m.group(0), "ip"), text)
    return SanitizeResult(text=text, mappings=mappings)


def restore(text: str, mappings: list[MaskMapping]) -> str:
    """本地还原（仅用于落库产物；还原结果不出域）。"""
    for mapping in mappings:
        text = text.replace(mapping.placeholder, mapping.original)
    return text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
