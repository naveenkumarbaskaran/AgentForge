"""
Test Suite for AgentForge — Intent Classification Cascade

Run:  pytest tests/ -v
"""

import pytest
from agentforge.patterns.intent import IntentCascade, IntentMatch


class TestIntentCascadeRegex:
    """Level 1: Regex-based classification — fastest, highest confidence."""

    @pytest.fixture
    def cascade(self):
        return IntentCascade()

    # ─── Order Summary Intent ────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Show me order 4002310",
        "order summary for 4002310",
        "What's the status of order 4002310?",
        "Order details 4002310",
        "maintenance order 4002310",
    ])
    def test_order_summary_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "order_summary"
        assert result.confidence >= 0.95
        assert result.method == "regex"

    # ─── Cost Intent ─────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Show costs for 4002310",
        "What are the costs?",
        "cost breakdown",
        "How much has been spent on order 4002310?",
    ])
    def test_costs_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "costs"
        assert result.method == "regex"

    # ─── Confirmations Intent ────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Show confirmations",
        "work done on this order",
        "time entries",
        "missing conf",
    ])
    def test_confirmations_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "confirmations"

    # ─── Operations Intent ───────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Show operations",
        "work steps for order 4002310",
        "task list",
        "list activities",
    ])
    def test_operations_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "operations"

    # ─── Search Intent ───────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Search for overdue orders",
        "Find all critical orders",
        "List pending maintenance",
        "Show all open orders",
    ])
    def test_search_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "search"

    # ─── Close/TECO Intent ───────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Close order 4002310",
        "TECO this order",
        "technically complete 4002310",
        "finish order 4002310",
    ])
    def test_close_order_detected(self, cascade, query):
        result = cascade.classify(query)
        assert result is not None
        assert result.intent == "close_order"

    # ─── No Match → LLM Fallback ────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Hello",
        "What can you do?",
        "Tell me a joke",
        "How's the weather?",
    ])
    def test_unknown_returns_none(self, cascade, query):
        """Unknown queries should return None → triggers LLM fallback."""
        result = cascade.classify(query)
        assert result is None


class TestIntentCascadeParameterExtraction:
    """Test that order IDs and other params are extracted correctly."""

    @pytest.fixture
    def cascade(self):
        return IntentCascade()

    def test_extracts_order_id_7_digit(self, cascade):
        result = cascade.classify("Show order 4002310")
        assert result.parameters.get("order_id") == "4002310"

    def test_extracts_order_id_starting_with_3(self, cascade):
        result = cascade.classify("order summary 3000001")
        assert result.parameters.get("order_id") == "3000001"

    def test_no_order_id_when_absent(self, cascade):
        result = cascade.classify("Show all costs")
        assert "order_id" not in result.parameters or result.parameters.get("order_id") is None

    def test_extracts_plant(self, cascade):
        result = cascade.classify("Find overdue orders in plant 1000")
        assert result.parameters.get("plant") == "1000"

    def test_does_not_extract_random_numbers_as_order(self, cascade):
        """5-digit or 8-digit numbers should NOT be treated as order IDs."""
        result = cascade.classify("Show costs for 12345")
        if result:
            assert "order_id" not in result.parameters


class TestIntentCascadeCustomPatterns:
    """Test adding custom patterns at runtime."""

    def test_add_custom_pattern(self):
        cascade = IntentCascade()
        cascade.add_pattern("warranty", r"\bwarranty\b|\bguarantee\b")

        result = cascade.classify("Is this under warranty?")
        assert result is not None
        assert result.intent == "warranty"

    def test_custom_patterns_in_constructor(self):
        cascade = IntentCascade(patterns={
            "greeting": [r"\bhello\b|\bhi\b|\bhey\b"],
        })

        result = cascade.classify("Hello there!")
        assert result is not None
        assert result.intent == "greeting"
