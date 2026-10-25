"""单元测试：SSE 事件载荷与帧格式（契约 /realtime/stream）。"""

from __future__ import annotations

from huntai.realtime.hub import RealtimeEvent, _frame, _xread_entries


def test_event_payload_minimal_fields():
    event = RealtimeEvent(
        topic="alerts", name="alert.updated", resource="alert", resource_id=7, team="platform"
    )

    payload = event.payload()

    assert payload["resource"] == "alert"
    assert payload["resource_id"] == 7
    assert payload["team"] == "platform"
    assert payload["occurred_at"].endswith("Z")


def test_sse_frame_shape():
    frame = _frame("1729730000000-0", {"name": "alert.updated", "data": '{"resource_id": 7}'})

    assert frame == (
        "id: 1729730000000-0\n"
        "event: alert.updated\n"
        'data: {"resource_id": 7}\n\n'
    )


def test_xread_entries_parses_redis_py_shape():
    # redis-py XREAD 返回 [(stream_key, [(id, fields), ...])]
    assert _xread_entries(None) == []
    assert _xread_entries([]) == []
    assert _xread_entries(
        [("huntai:events", [("1-0", {"topic": "alerts", "name": "alert.updated"})])]
    ) == [("1-0", {"topic": "alerts", "name": "alert.updated"})]
