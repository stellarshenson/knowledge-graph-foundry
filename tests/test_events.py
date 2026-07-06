"""Tests for the event system."""

import json

from knowledge_graph_foundry.events import (
    disable_event_log,
    emit,
    enable_event_log,
    subscribe,
    unsubscribe,
)


class TestSignals:
    def test_subscriber_receives_payload(self):
        seen = []

        def receiver(sender, **kw):
            seen.append(kw)

        subscribe("document.completed", receiver)
        try:
            emit("document.completed", document_id="d1", entities=5)
        finally:
            unsubscribe("document.completed", receiver)
        assert seen == [{"document_id": "d1", "entities": 5}]


class TestEventLog:
    def test_jsonl_capture(self, tmp_path):
        log = tmp_path / "events.jsonl"
        enable_event_log(log)
        try:
            emit("resolution.merge", left="a", right="b", posterior=0.91)
            emit("curing.cured", document_index=4)
        finally:
            disable_event_log()
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(lines) == 2
        assert lines[0]["event"] == "resolution.merge"
        assert lines[0]["posterior"] == 0.91
        assert "ts" in lines[0]
        assert lines[1]["event"] == "curing.cured"

    def test_no_log_when_disabled(self, tmp_path):
        emit("load.completed", count=1)  # must not raise
