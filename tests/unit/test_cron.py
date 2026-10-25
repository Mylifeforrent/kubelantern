"""单元测试：cron 匹配器。"""

from datetime import UTC, datetime

import pytest

from huntai.core.cron import parse_cron


def test_every_minute():
    cron = parse_cron("* * * * *")
    assert cron.matches(datetime(2026, 10, 25, 8, 0, tzinfo=UTC))
    assert cron.matches(datetime(2026, 10, 25, 8, 59, tzinfo=UTC))


def test_step_minutes():
    cron = parse_cron("*/5 * * * *")
    assert cron.matches(datetime(2026, 10, 25, 8, 5, tzinfo=UTC))
    assert cron.matches(datetime(2026, 10, 25, 8, 0, tzinfo=UTC))
    assert not cron.matches(datetime(2026, 10, 25, 8, 3, tzinfo=UTC))


def test_range_and_list():
    cron = parse_cron("0 9-17 * * 1,3")
    assert cron.matches(datetime(2026, 10, 26, 9, 0, tzinfo=UTC))  # 周一
    assert cron.matches(datetime(2026, 10, 28, 17, 0, tzinfo=UTC))  # 周三
    assert not cron.matches(datetime(2026, 10, 28, 18, 0, tzinfo=UTC))
    assert not cron.matches(datetime(2026, 10, 27, 9, 0, tzinfo=UTC))  # 周二


def test_sunday_zero_and_seven():
    zero = parse_cron("0 0 * * 0")
    seven = parse_cron("0 0 * * 7")
    sunday = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
    assert zero.matches(sunday) and seven.matches(sunday)


def test_day_and_dow_union_semantics():
    cron = parse_cron("0 0 13 * 5")
    assert cron.matches(datetime(2026, 11, 13, 0, 0, tzinfo=UTC))  # 恰逢 13 日与周五 → 命中
    assert cron.matches(datetime(2026, 10, 30, 0, 0, tzinfo=UTC))  # 周五（日不受限）
    assert not cron.matches(datetime(2026, 11, 12, 0, 0, tzinfo=UTC))  # 周四且非 13 日


def test_matches_between():
    cron = parse_cron("30 * * * *")
    start = datetime(2026, 10, 25, 8, 10, tzinfo=UTC)
    end = datetime(2026, 10, 25, 8, 29, tzinfo=UTC)
    assert not cron.matches_between(start, end)
    assert cron.matches_between(start, datetime(2026, 10, 25, 8, 31, tzinfo=UTC))


@pytest.mark.parametrize("expr", ["* * * *", "*/0 * * * *", "61 * * * *", "* 24 * * *", "a * * * *"])
def test_invalid_expressions(expr):
    with pytest.raises(ValueError):
        parse_cron(expr)
