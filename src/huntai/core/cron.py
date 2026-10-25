"""五字段分钟粒度 cron 匹配器（替代候选依赖 croniter，P0 依赖审计前不引入）。

支持：`*`、`a`、`a-b`、`*/n`、`a-b/n`、逗号列表；字段序 分 时 日 月 周。
周日为 0 与 7（同 cron）。语义只做「该分钟是否命中」，供巡检调度 tick 判定到期。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_MINUTE, _HOUR, _DAY, _MONTH, _DOW = range(5)
_FULL_SETS = (
    frozenset(range(0, 60)),
    frozenset(range(0, 24)),
    frozenset(range(1, 32)),
    frozenset(range(1, 13)),
    frozenset(range(0, 7)),
)


@dataclass(frozen=True)
class CronExpr:
    sets: tuple[frozenset[int], frozenset[int], frozenset[int], frozenset[int], frozenset[int]]

    def matches(self, dt: datetime) -> bool:
        values = (dt.minute, dt.hour, dt.day, dt.month, dt.isoweekday() % 7)
        if not all(values[i] in self.sets[i] for i in (_MINUTE, _HOUR, _MONTH)):
            return False
        day_hit = values[_DAY] in self.sets[_DAY]
        dow_hit = values[_DOW] in self.sets[_DOW]
        day_restricted = self.sets[_DAY] != _FULL_SETS[_DAY]
        dow_restricted = self.sets[_DOW] != _FULL_SETS[_DOW]
        # cron 语义：日与周都受限时，任一命中即可
        if day_restricted and dow_restricted:
            return day_hit or dow_hit
        return day_hit and dow_hit

    def matches_between(self, start: datetime, end: datetime) -> bool:
        """[start, end) 内是否存在命中分钟（按分钟步进，步数封顶防失控）。"""
        if end <= start:
            return False
        cursor = start.replace(second=0, microsecond=0)
        if cursor < start:
            cursor += timedelta(minutes=1)
        steps = 0
        while cursor < end:
            if self.matches(cursor):
                return True
            cursor += timedelta(minutes=1)
            steps += 1
            if steps >= 60 * 24 * 366:
                return False
        return False


def _parse_field(spec: str, low: int, high: int, *, is_dow: bool = False) -> frozenset[int]:
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"cron 字段为空：{spec}")
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step < 1:
                raise ValueError(f"cron 步长非法：{part}")
        else:
            base = part
        if base == "*":
            start, end = low, high
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(base)
        if start < low or end > high or start > end:
            raise ValueError(f"cron 取值越界：{part}（允许 {low}-{high}）")
        values.update(range(start, end + 1, step))
    if is_dow:
        if 7 in values:
            values.add(0)
        values.discard(7)
    return frozenset(values)


def parse_cron(expr: str) -> CronExpr:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"cron 表达式必须为 5 字段：{expr}")
    ranges = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    sets: list[frozenset[int]] = []
    for (low, high), spec in zip(ranges, parts, strict=True):
        sets.append(_parse_field(spec, low, high, is_dow=(len(sets) == _DOW)))
    return CronExpr(tuple(sets))
