"""预算检查（BR-03：默认 40 次调用 / 100k 输出 token；超限 graceful 终止）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetVerdict:
    allowed: bool
    reason: str | None = None


def check_before_call(budget: dict, *, calls_used: int, tokens_used: int) -> BudgetVerdict:
    if calls_used >= int(budget.get("max_calls", 0)):
        return BudgetVerdict(False, f"调用次数已达上限 {budget.get('max_calls')}（BR-03）")
    if tokens_used >= int(budget.get("max_output_tokens", 0)):
        return BudgetVerdict(False, f"输出 token 已达上限 {budget.get('max_output_tokens')}（BR-03）")
    return BudgetVerdict(True)
