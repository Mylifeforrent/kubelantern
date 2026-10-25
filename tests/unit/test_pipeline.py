"""单元测试：归一化 / 指纹 / 富化 / 关联（pipeline 纯函数）。"""

from datetime import UTC, datetime

from huntai.pipeline import correlate, enrich, normalizer


def _labels(**kwargs):
    return kwargs


def test_normalize_alertmanager_shape():
    payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighErrorRate", "namespace": "api", "severity": "critical"},
                "annotations": {"summary": "错误率过高"},
                "startsAt": "2026-10-24T08:00:00Z",
            }
        ],
    }
    result = normalizer.normalize(payload, fingerprint_fields=["alertname", "namespace"])
    assert result.severity == "critical"
    assert result.title == "错误率过高"
    assert result.is_resolve is False
    assert result.occurred_at == datetime(2026, 10, 24, 8, 0, tzinfo=UTC)
    assert len(result.fingerprint) == 64


def test_normalize_generic_shape_and_severity_map():
    payload = {"severity": "P0", "labels": {"alertname": "X", "namespace": "default"}}
    result = normalizer.normalize(payload, fingerprint_fields=[])
    assert result.severity == "critical"
    assert result.labels["alertname"] == "X"


def test_normalize_resolve_event():
    payload = {"status": "resolved", "labels": {"alertname": "X"}}
    result = normalizer.normalize(payload, fingerprint_fields=[])
    assert result.is_resolve is True


def test_fingerprint_stable_and_volatile_excluded():
    base = {"alertname": "X", "namespace": "prod", "timestamp": 123}
    other = {"alertname": "X", "namespace": "prod", "timestamp": 999}
    a = normalizer.normalize({"labels": base}, fingerprint_fields=[])
    b = normalizer.normalize({"labels": other}, fingerprint_fields=[])
    assert a.fingerprint == b.fingerprint


def test_fingerprint_differs_by_fields():
    a = normalizer.normalize({"labels": {"alertname": "A", "namespace": "x"}}, fingerprint_fields=["alertname"])
    b = normalizer.normalize({"labels": {"alertname": "B", "namespace": "x"}}, fingerprint_fields=["alertname"])
    assert a.fingerprint != b.fingerprint


def test_enrich_matchers_and_mappings():
    rules = [
        (
            [{"field": "namespace", "operator": "contains", "value": "prod"}],
            [
                {"type": "extraction", "source": "team_label", "target": "team"},
                {"type": "mapping", "target": "env", "value": "production"},
            ],
            10,
        ),
        ([{"field": "missing", "operator": "exists"}], [{"type": "mapping", "target": "x", "value": "1"}], 5),
    ]
    enrichments = enrich.apply_enrichments(rules, {"namespace": "team-prod", "team_label": "platform"})
    assert enrichments == {"team": "platform", "env": "production"}


def test_enrich_operators():
    matchers_eq = [{"field": "env", "operator": "eq", "value": "prod"}]
    assert enrich.match_rule(matchers_eq, {"env": "prod"})
    assert not enrich.match_rule(matchers_eq, {"env": "staging"})
    matchers_in = [{"field": "env", "operator": "in", "value": ["prod", "staging"]}]
    assert enrich.match_rule(matchers_in, {"env": "staging"})
    matchers_ne = [{"field": "env", "operator": "ne", "value": "prod"}]
    assert enrich.match_rule(matchers_ne, {"env": "dev"})
    matchers_regex = [{"field": "ns", "operator": "regex", "value": r"^team-"}]
    assert enrich.match_rule(matchers_regex, {"ns": "team-pay"})
    assert not enrich.match_rule([{"field": "env", "operator": "eq", "value": "x"}], {})


CONDITIONS = {
    "op": "AND",
    "rules": [{"field": "namespace", "operator": "eq", "value": "prod"}],
    "group_by": ["namespace"],
}


def test_correlate_conditions_and_group():
    attrs = {"namespace": "prod", "severity": "critical"}
    assert correlate.conditions_match(CONDITIONS, attrs)
    assert correlate.group_key(CONDITIONS, attrs) == ("prod",)
    assert not correlate.conditions_match(CONDITIONS, {"namespace": "dev"})
    or_conditions = {"op": "OR", "rules": [
        {"field": "a", "operator": "eq", "value": "1"},
        {"field": "b", "operator": "eq", "value": "2"},
    ]}
    assert correlate.conditions_match(or_conditions, {"b": "2"})
    assert not correlate.conditions_match(or_conditions, {"a": "9", "b": "9"})
