"""富化规则匹配（纯函数，04-backend-design §3.2.2 步骤 2）。

matchers 结构 [ASSUMPTION]（P0 管道详设评审）：
  [{"field": "namespace", "operator": "eq", "value": "prod"}]  —— 规则内 AND
  operator ∈ eq / ne / in / contains / exists / regex
mappings 结构（Keep 范式）：
  [{"type": "extraction", "source": "namespace", "target": "team"}]  —— 从 labels 提取
  [{"type": "mapping", "target": "env", "value": "production"}]      —— 常量映射
"""

from __future__ import annotations

import re
from typing import Any


def _predicate_holds(label_value: str | None, operator: str, expected: Any) -> bool:
    if operator == "exists":
        return label_value is not None
    if label_value is None:
        return False
    if operator == "eq":
        return label_value == str(expected)
    if operator == "ne":
        return label_value != str(expected)
    if operator == "contains":
        return str(expected) in label_value
    if operator == "in":
        candidates = expected if isinstance(expected, list) else [expected]
        return label_value in {str(c) for c in candidates}
    if operator == "regex":
        try:
            return re.search(str(expected), label_value) is not None
        except re.error:
            return False
    return False


def match_rule(matchers: Any, labels: dict[str, str]) -> bool:
    if isinstance(matchers, dict):
        matchers = [matchers]
    if not matchers:
        return False
    for matcher in matchers:
        if not isinstance(matcher, dict):
            continue
        field = str(matcher.get("field", ""))
        operator = str(matcher.get("operator", "eq"))
        expected = matcher.get("value")
        if not _predicate_holds(labels.get(field), operator, expected):
            return False
    return True


def apply_enrichments(rules: list[tuple[Any, Any, int]], labels: dict[str, str]) -> dict[str, Any]:
    """rules: [(matchers, mappings, priority)]；命中按 priority 升序应用，后命中覆盖先命中。"""
    enrichments: dict[str, Any] = {}
    for matchers, mappings, _priority in sorted(rules, key=lambda r: r[2]):
        if not match_rule(matchers, labels):
            continue
        for mapping in mappings or []:
            if not isinstance(mapping, dict):
                continue
            mapping_type = mapping.get("type", "mapping")
            target = mapping.get("target")
            if not target:
                continue
            if mapping_type == "extraction":
                source_value = labels.get(str(mapping.get("source", "")))
                if source_value is not None:
                    enrichments[str(target)] = source_value
            else:  # mapping 常量
                if "value" in mapping:
                    enrichments[str(target)] = mapping["value"]
    return enrichments
