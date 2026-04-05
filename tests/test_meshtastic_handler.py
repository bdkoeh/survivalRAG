"""Unit tests for MeshtasticBridge receive handler and deduplication.

Tests the message filtering, trigger prefix handling, and deduplication logic
without requiring the meshtastic package or real hardware.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from pipeline.meshtastic_bridge import MeshtasticBridge, load_config


def _make_bridge(overrides=None):
    """Create a bridge with test config, mocking the meshtastic interface."""
    config = {
        "enabled": True,
        "connection": "serial",
        "channel": 0,
        "trigger": "?",
        "chunk_size": 194,
        "max_parts": 5,
        "chunk_delay": 0.01,  # Fast for tests
        "response_mode": "compact",
        "bot_prefix": "[RAG]",
    }
    if overrides:
        config.update(overrides)

    bridge = MeshtasticBridge(config)
    bridge.interface = MagicMock()
    bridge._my_node_id = "!aabbccdd"
    bridge._running = True
    return bridge


def _make_packet(text, from_id="!11223344", channel=0, packet_id=1):
    """Create a mock Meshtastic packet."""
    return {
        "decoded": {"text": text},
        "fromId": from_id,
        "toId": "!aabbccdd",
        "channel": channel,
        "id": packet_id,
        "rxSnr": 10.0,
        "rxRssi": -50,
        "hopsAway": 1,
    }


# ---------------------------------------------------------------------------
# Message filtering
# ---------------------------------------------------------------------------

class TestReceiveFiltering:
    def test_ignore_non_text_packet(self):
        bridge = _make_bridge()
        packet = {"decoded": {}, "fromId": "!11223344", "channel": 0, "id": 1}
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_ignore_empty_text(self):
        bridge = _make_bridge()
        packet = _make_packet("")
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_ignore_self_message(self):
        bridge = _make_bridge()
        packet = _make_packet("?how to purify water", from_id="!aabbccdd")
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_ignore_wrong_channel(self):
        bridge = _make_bridge()
        packet = _make_packet("?how to purify water", channel=3)
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_ignore_bot_prefix_message(self):
        bridge = _make_bridge()
        packet = _make_packet("[RAG] Some response text")
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_ignore_without_trigger_prefix(self):
        bridge = _make_bridge()
        packet = _make_packet("how to purify water")  # Missing ?
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()

    def test_trigger_prefix_stripped(self):
        """Query text should have trigger prefix removed."""
        bridge = _make_bridge()
        packet = _make_packet("?how to purify water")

        # Mock _handle_query to capture the query text
        queries = []
        def capture_query(text, sender):
            queries.append(text)

        with patch.object(bridge, '_handle_query_safe', side_effect=capture_query):
            bridge._on_receive(packet, bridge.interface)

        # Should have sent "Thinking..." ack
        bridge.interface.sendText.assert_called_once()
        call_args = bridge.interface.sendText.call_args
        assert "Thinking" in call_args[0][0]

        # Query should be stripped of trigger
        assert queries == ["how to purify water"]

    def test_empty_trigger_responds_to_all(self):
        """With empty trigger, respond to all messages."""
        bridge = _make_bridge({"trigger": ""})
        packet = _make_packet("how to purify water")

        with patch.object(bridge, '_handle_query_safe'):
            bridge._on_receive(packet, bridge.interface)

        # Should have sent "Thinking..." ack (meaning it accepted the message)
        bridge.interface.sendText.assert_called_once()

    def test_query_only_whitespace_after_trigger(self):
        bridge = _make_bridge()
        packet = _make_packet("?   ")
        bridge._on_receive(packet, bridge.interface)
        bridge.interface.sendText.assert_not_called()


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_ignored(self):
        bridge = _make_bridge()
        packet = _make_packet("?test query", packet_id=42)

        call_count = 0
        def counting_handler(text, sender):
            nonlocal call_count
            call_count += 1

        with patch.object(bridge, '_handle_query_safe', side_effect=counting_handler):
            bridge._on_receive(packet, bridge.interface)
            bridge._on_receive(packet, bridge.interface)  # Same packet_id

        assert call_count == 1

    def test_different_packet_ids_not_deduplicated(self):
        bridge = _make_bridge()
        # Dedup is keyed on (packet_id, from_id) — different IDs should not collide
        assert not bridge._is_duplicate(1, "!11223344")
        assert not bridge._is_duplicate(2, "!11223344")

    def test_same_id_different_sender_not_deduplicated(self):
        bridge = _make_bridge()
        assert not bridge._is_duplicate(1, "!11223344")
        assert not bridge._is_duplicate(1, "!55667788")

    def test_stale_entries_evicted(self):
        bridge = _make_bridge()
        # Insert an old entry
        bridge._seen_packets[(99, "!old")] = time.time() - 120  # 2 min old

        # This should evict the old entry
        assert not bridge._is_duplicate(1, "!new")
        assert (99, "!old") not in bridge._seen_packets


# ---------------------------------------------------------------------------
# Busy handling
# ---------------------------------------------------------------------------

class TestBusyHandling:
    def test_busy_response_when_overloaded(self):
        bridge = _make_bridge()
        bridge._pending_count = 2  # Already at capacity

        packet = _make_packet("?test query")
        bridge._on_receive(packet, bridge.interface)

        # Should have sent both "Thinking..." and "Busy" -- wait, no.
        # With pending_count >= 2, it should send "Busy" instead of "Thinking..."
        calls = bridge.interface.sendText.call_args_list
        busy_sent = any("Busy" in str(call) for call in calls)
        assert busy_sent


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_defaults(self):
        config = load_config()
        assert config["enabled"] is False
        assert config["connection"] == "serial"
        assert config["channel"] == 0
        assert config["trigger"] == "?"
        assert config["chunk_size"] == 194
        assert config["max_parts"] == 5
        assert config["chunk_delay"] == 2.0
        assert config["response_mode"] == "compact"
        assert config["bot_prefix"] == "[RAG]"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("MESHTASTIC_ENABLED", "true")
        monkeypatch.setenv("MESHTASTIC_CHANNEL", "3")
        monkeypatch.setenv("MESHTASTIC_TRIGGER", "!ask")
        monkeypatch.setenv("MESHTASTIC_MAX_PARTS", "7")
        monkeypatch.setenv("MESHTASTIC_CHUNK_DELAY", "5.0")

        config = load_config()
        assert config["enabled"] is True
        assert config["channel"] == 3
        assert config["trigger"] == "!ask"
        assert config["max_parts"] == 7
        assert config["chunk_delay"] == 5.0
