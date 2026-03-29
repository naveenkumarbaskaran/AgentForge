"""
Test Suite for AgentForge — Response Models & A2A Protocol Output
"""

import pytest
from agentforge.models.response import AgentResponse
from agentforge.models.plan import ExecutionPlan, ObserverVerdict


class TestAgentResponse:
    """Response object structure and helper methods."""

    def test_basic_response(self):
        resp = AgentResponse(text="Order 4002310 is open", token_count=150)
        assert resp.text == "Order 4002310 is open"
        assert resp.is_error is False
        assert resp.is_hitl is False

    def test_error_response(self):
        resp = AgentResponse.error("Something went wrong")
        assert resp.is_error is True
        assert "Something went wrong" in resp.text

    def test_hitl_response(self):
        resp = AgentResponse.hitl_confirmation(
            action="close_order",
            summary="Close order 4002310"
        )
        assert resp.is_hitl is True
        assert "Confirmation Required" in resp.text
        assert len(resp.quick_replies) == 2
        assert resp.quick_replies[0]["title"] == "Yes, proceed"
        assert resp.quick_replies[1]["title"] == "No, cancel"

    def test_to_a2a_parts(self):
        """Response converts to A2A protocol parts format."""
        resp = AgentResponse(
            text="Here's your order",
            card={"type": "List", "items": []},
            quick_replies=[{"title": "Show costs", "value": "costs"}],
        )
        parts = resp.to_parts()
        assert len(parts) == 3
        assert parts[0]["kind"] == "text"
        assert parts[1]["kind"] == "data"
        assert parts[2]["kind"] == "data"

    def test_parts_without_card(self):
        resp = AgentResponse(text="No card data")
        parts = resp.to_parts()
        assert len(parts) == 1
        assert parts[0]["kind"] == "text"


class TestExecutionPlan:
    """Planner output model."""

    def test_from_json(self):
        json_str = '{"intent": "order_summary", "confidence": 0.95, "tools_needed": ["get_order", "get_costs"], "parameters": {"order_id": "4002310"}, "reasoning": "User asked for order details"}'
        plan = ExecutionPlan.from_json(json_str, query="Show order 4002310")

        assert plan.intent == "order_summary"
        assert plan.confidence == 0.95
        assert "get_order" in plan.tools_needed
        assert plan.parameters["order_id"] == "4002310"
        assert plan.query == "Show order 4002310"

    def test_to_instruction(self):
        plan = ExecutionPlan(
            intent="costs",
            confidence=0.9,
            tools_needed=["get_costs"],
            parameters={"order_id": "4002310"},
            reasoning="User wants cost breakdown",
        )
        instruction = plan.to_instruction()
        assert "costs" in instruction
        assert "get_costs" in instruction
        assert "4002310" in instruction

    def test_to_dict_roundtrip(self):
        plan = ExecutionPlan(
            intent="search",
            confidence=0.8,
            tools_needed=["search_orders"],
            parameters={"plant": "1000"},
            reasoning="Search query",
        )
        d = plan.to_dict()
        assert d["intent"] == "search"
        assert d["tools_needed"] == ["search_orders"]


class TestObserverVerdict:
    """Observer output model."""

    def test_pass_verdict(self):
        verdict = ObserverVerdict.from_json({
            "pass": True,
            "reason": "All tools executed successfully",
        })
        assert verdict.passed is True
        assert verdict.requires_hitl is False
        assert verdict.retry is False

    def test_hitl_verdict(self):
        verdict = ObserverVerdict.from_json({
            "pass": False,
            "reason": "Write operation detected",
            "requires_hitl": True,
            "write_action": "close_order",
            "write_summary": "Close order 4002310",
        })
        assert verdict.passed is False
        assert verdict.requires_hitl is True
        assert verdict.write_action == "close_order"

    def test_retry_verdict(self):
        verdict = ObserverVerdict.from_json({
            "pass": False,
            "reason": "Missing data, need to retry with broader filter",
            "retry": True,
        })
        assert verdict.retry is True
