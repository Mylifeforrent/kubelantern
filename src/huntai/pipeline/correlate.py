"""关联引擎（BR-04，纯函数部分；分组与候选落库在 alerts/incidents service）。

conditions 结构 [ASSUMPTION]（P2 事件域详设评审）：
  {
    "op": "AND" | "OR",
    "rules": [{"field": "namespace", "operator": "eq", "value": "prod"}],
    "group_by": ["namespace"]          # 可选：同组才可关联
  }
  field 在 labels 与 enrichments 合并视图上求值。
"""

from __future__ import annotations

from typing import Any

from huntai.pipeline.enrich import _predicate_holds


def conditions_match(conditions: Any, attributes: dict[str, Any]) -> bool:
    if not isinstance(conditions, dict):
        return False
    rules = conditions.get("rules")
    if not isinstance(rules, list) or not rules:
        return False
    op = str(conditions.get("op", "AND")).upper()
    results: list[bool] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field", ""))
        operator = str(rule.get("operator", "eq"))
        expected = rule.get("value")
        results.append(_predicate_holds(str(attributes.get(field, "")) if field in attributes else None, operator, expected))
    if not results:
        return False
    return all(results) if op == "AND" else any(results)


def group_key(conditions: Any, attributes: dict[str, Any]) -> tuple:
    group_by = conditions.get("group_by", []) if isinstance(conditions, dict) else []
    if not isinstance(group_by, list):
        group_by = []
    return tuple(str(attributes.get(str(field), "")) for field in group_by)


def rule_signature(rule_id: int, key: tuple) -> str:
    return f"{rule_id}:{'/'.join(key)}"
