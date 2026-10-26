"""单元测试：AI 网关纯函数（脱敏往返 / 预算 / 熔断 / 路由）。"""

import pytest

from huntai.core.config import Settings
from huntai.gateway import router, sanitizer
from huntai.gateway.budget import check_before_call
from huntai.gateway.circuit import CircuitBreaker


def test_route_prefers_external_only_when_egress_fully_configured():
    external = Settings(
        ai_egress_enabled=True,
        ai_external_url="https://api.deepseek.com/v1",
        ai_external_model="deepseek-chat",
        ai_external_key_ref="env:HUNTAI_AI_EXTERNAL_KEY",
    )
    assert router.route("explain", external) == "external"

    no_egress = Settings(
        ai_egress_enabled=False,
        ai_external_url="https://api.deepseek.com/v1",
        ai_external_key_ref="env:HUNTAI_AI_EXTERNAL_KEY",
    )
    assert router.route("explain", no_egress) == "local"

    missing_url = Settings(
        ai_egress_enabled=True,
        ai_external_url=None,
        ai_external_key_ref="env:HUNTAI_AI_EXTERNAL_KEY",
    )
    assert router.route("explain", missing_url) == "local"
    assert router.route("explain") == "local"


def test_sanitize_masks_known_terms_and_restore():
    text = "Pod web-abc123 in namespace payment-prod 连续崩溃"
    result = sanitizer.sanitize(text, known_terms={"payment-prod": "namespace", "web-abc123": "pod"})
    assert "payment-prod" not in result.text
    assert "web-abc123" not in result.text
    assert result.text.count("K8S_MASK_") == 2
    assert sanitizer.restore(result.text, result.mappings) == text


def test_sanitize_masks_ip_and_credentials():
    text = "node 10.1.2.3 报错；password=SuperSecret123 泄漏"
    result = sanitizer.sanitize(text)
    assert "10.1.2.3" not in result.text
    assert "SuperSecret123" not in result.text
    kinds = {mapping.kind for mapping in result.mappings}
    assert "ip" in kinds and "credential" in kinds
    restored = sanitizer.restore(result.text, result.mappings)
    assert "10.1.2.3" in restored and "SuperSecret123" in restored


def test_sanitize_no_mask_on_plain_text():
    result = sanitizer.sanitize("一切正常，无需处理")
    assert result.text == "一切正常，无需处理"
    assert result.mappings == []


def test_budget_allows_until_limits():
    budget = {"max_calls": 2, "max_output_tokens": 100}
    assert check_before_call(budget, calls_used=0, tokens_used=0).allowed
    assert check_before_call(budget, calls_used=1, tokens_used=50).allowed
    blocked_calls = check_before_call(budget, calls_used=2, tokens_used=10)
    assert not blocked_calls.allowed and "调用次数" in blocked_calls.reason
    blocked_tokens = check_before_call(budget, calls_used=1, tokens_used=100)
    assert not blocked_tokens.allowed and "token" in blocked_tokens.reason


def test_circuit_opens_after_threshold_and_half_open():
    breaker = CircuitBreaker(failure_threshold=2, reset_seconds=60)
    assert breaker.allow()
    assert breaker.record_failure() is None
    assert breaker.record_failure() == "circuit_opened"
    assert not breaker.allow()  # 开路期拒绝
    breaker._opened_at -= 120  # 模拟静默期已过 → 半开放行探测
    assert breaker.allow()
    breaker.record_success()  # 半开探测成功 → 闭合
    assert breaker.allow()
