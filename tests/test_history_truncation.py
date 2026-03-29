"""
Test Suite for AgentForge — History Windowing & Result Truncation
"""

import pytest
import json
from agentforge.patterns.history import HistoryWindow
from agentforge.patterns.truncation import ResultTruncator


# ═══════════════════════════════════════════════════════════════════
#  HISTORY WINDOWING
# ═══════════════════════════════════════════════════════════════════

class TestHistoryWindow:
    """Sliding window keeps only last N turns for the planner."""

    def test_window_keeps_last_n_turns(self):
        hw = HistoryWindow(max_turns=3)

        for i in range(10):
            hw.add_turn(f"user message {i}", f"assistant reply {i}")

        window = hw.get_window()
        # 3 turns = 6 messages (user + assistant each)
        assert len(window) == 6
        # Should contain turns 7, 8, 9 (last 3)
        assert "user message 7" in window[0]["content"]
        assert "user message 9" in window[4]["content"]

    def test_full_history_retained(self):
        hw = HistoryWindow(max_turns=3)

        for i in range(10):
            hw.add_turn(f"user {i}", f"assistant {i}")

        full = hw.get_full_history()
        # All 10 turns = 20 messages
        assert len(full) == 20

    def test_turn_count(self):
        hw = HistoryWindow(max_turns=3)
        assert hw.turn_count == 0

        hw.add_turn("hi", "hello")
        assert hw.turn_count == 1

        hw.add_turn("how?", "fine")
        assert hw.turn_count == 2

    def test_clear_resets_everything(self):
        hw = HistoryWindow(max_turns=3)
        hw.add_turn("hi", "hello")
        hw.clear()

        assert hw.turn_count == 0
        assert hw.get_window() == []
        assert hw.get_full_history() == []

    def test_window_message_format(self):
        hw = HistoryWindow(max_turns=2)
        hw.add_turn("What's order 4002310?", "Order 4002310 is a pump repair.")

        window = hw.get_window()
        assert window[0] == {"role": "user", "content": "What's order 4002310?"}
        assert window[1] == {"role": "assistant", "content": "Order 4002310 is a pump repair."}

    def test_max_messages_cap(self):
        """Full history is also capped to prevent unbounded growth."""
        hw = HistoryWindow(max_turns=3, max_messages=10)

        for i in range(100):
            hw.add_turn(f"user {i}", f"assistant {i}")

        full = hw.get_full_history()
        # 10 messages = 5 turns worth (user + assistant)
        assert len(full) == 10


# ═══════════════════════════════════════════════════════════════════
#  RESULT TRUNCATION
# ═══════════════════════════════════════════════════════════════════

class TestResultTruncation:
    """Cap API responses to prevent context window overflow."""

    @pytest.fixture
    def truncator(self):
        return ResultTruncator(max_kb=1, max_items=5)  # 1KB for easy testing

    def test_small_result_passes_untouched(self, truncator):
        """Results under the limit should not be modified."""
        data = {"order_id": "4002310", "status": "open"}
        result = truncator.truncate(data)
        assert result == data

    def test_large_list_is_truncated(self, truncator):
        """Lists exceeding max_items are capped."""
        items = [{"id": i, "value": f"item_{i}" * 50} for i in range(100)]
        result = truncator.truncate(items)

        assert result["_truncated"] is True
        assert result["_total_items"] == 100
        assert result["_shown_items"] == 5
        assert len(result["items"]) == 5

    def test_large_dict_truncates_big_values(self, truncator):
        """Dicts with oversized nested values get truncated."""
        data = {
            "header": {"id": "123"},
            "huge_field": "x" * 5000,  # Way over 1KB
        }
        result = truncator.truncate(data)
        assert result["_truncated"] is True
        assert "[TRUNCATED" in str(result.get("huge_field", ""))

    def test_string_truncation(self, truncator):
        """Long strings are hard-cut at the byte limit."""
        long_text = "A" * 5000
        result = truncator.truncate(long_text)
        assert "[TRUNCATED" in result
        assert len(result) < 5000

    def test_50kb_default_cap(self):
        """Default 50KB cap handles realistic API responses."""
        truncator = ResultTruncator()  # Default 50KB
        # 50KB worth of data
        items = [{"id": i, "desc": f"description_{i}" * 10} for i in range(100)]
        result = truncator.truncate(items)
        # 100 items with ~150 bytes each = ~15KB → should pass
        assert isinstance(result, list)  # Not truncated
