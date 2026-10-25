"""payload 归一化 + fingerprint 计算（04-backend-design §3.2.1，纯函数）。

- 指纹字段取 providers.fingerprint_fields；为空时回退全部 labels（剔除易变键）[ASSUMPTION]。
- 兼容 Alertmanager / 通用 JSON 两种上报形态；恢复事件（status=resolved）驱动 resolve() [ASSUMPTION]。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

_VOLATILE_LABEL_KEYS = {"timestamp", "time", "value", "starts_at", "ends_at", "startsAt", "endsAt"}

SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "crit": "critical",
    "high": "critical",
    "p0": "critical",
    "p1": "critical",
    "sev1": "critical",
    "error": "critical",
    "warning": "warning",
    "warn": "warning",
    "p2": "warning",
    "sev2": "warning",
    "info": "info",
    "low": "info",
    "ok": "info",
    "none": "info",
    "p3": "info",
    "p4": "info",
    "sev3": "info",
    "resolved": "info",
}


@dataclass
class NormalizedAlert:
    fingerprint: str
    severity: str
    title: str | None
    labels: dict[str, str]
    occurred_at: datetime
    is_resolve: bool
    raw: dict = field(default_factory=dict, repr=False)


def normalize_severity(raw: object) -> str:
    return SEVERITY_MAP.get(str(raw or "").strip().lower(), "warning")


def _extract_alert_object(payload: dict) -> dict:
    """Alertmanager 一次上报可能带 alerts 数组：取最后一个作为本次事件。"""
    alerts = payload.get("alerts")
    if isinstance(alerts, list) and alerts and isinstance(alerts[-1], dict):
        merged = dict(payload)
        merged.update(alerts[-1])
        return merged
    return payload


def _parse_time(value: object, fallback: datetime) -> datetime:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (ValueError, OSError, OverflowError):
            return fallback
    if isinstance(value, str) and value:
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return fallback
    return fallback


def extract_labels(alert_obj: dict) -> dict[str, str]:
    labels = alert_obj.get("labels")
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items()}
    # 通用 JSON：顶层字符串字段视作标签
    reserved = {
        "status", "severity", "title", "summary", "timestamp", "time", "startsAt", "endsAt",
        "starts_at", "ends_at", "event", "alerts", "labels", "annotations", "message",
    }
    return {
        str(k): str(v) for k, v in alert_obj.items() if isinstance(v, (str, int, float, bool)) and k not in reserved
    }


def compute_fingerprint(fingerprint_fields: list, labels: dict[str, str]) -> str:
    if fingerprint_fields:
        selected = {k: labels.get(k, "") for k in fingerprint_fields}
    else:
        selected = {k: v for k, v in labels.items() if k not in _VOLATILE_LABEL_KEYS}
    canonical = json.dumps(selected, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def normalize(payload: dict, *, fingerprint_fields: list, now: datetime | None = None) -> NormalizedAlert:
    now = now or datetime.now(UTC)
    alert_obj = _extract_alert_object(payload)
    labels = extract_labels(alert_obj)

    annotations = alert_obj.get("annotations") if isinstance(alert_obj.get("annotations"), dict) else {}
    severity_raw = alert_obj.get("severity") or labels.get("severity") or annotations.get("severity")
    title = (
        alert_obj.get("title")
        or annotations.get("summary")
        or annotations.get("title")
        or labels.get("alertname")
        or labels.get("title")
    )

    status_text = str(alert_obj.get("status") or alert_obj.get("event") or "").lower()
    is_resolve = status_text in {"resolved", "firing_resolved", "closed"}

    occurred_at = _parse_time(
        alert_obj.get("startsAt") or alert_obj.get("starts_at") or alert_obj.get("timestamp") or alert_obj.get("time"),
        now,
    )

    return NormalizedAlert(
        fingerprint=compute_fingerprint(fingerprint_fields, labels),
        severity=normalize_severity(severity_raw),
        title=str(title) if title else None,
        labels=labels,
        occurred_at=occurred_at,
        is_resolve=is_resolve,
        raw=payload,
    )
