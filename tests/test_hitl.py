"""
Test Suite for AgentForge — HITL (Human-in-the-Loop) Write Safety Gate

Ensures no destructive operation can execute without human confirmation.
"""

import pytest
from agentforge.patterns.hitl import HITLGate, HITLRequest, HITLConfirmation


class TestHITLDetection:
    """Detect when a tool call needs human approval."""

    @pytest.fixture
    def gate(self):
        return HITLGate(enabled=True)

    # ─── Write Tools Require Confirmation ────────────────────────────

    @pytest.mark.parametrize("tool_name", [
        "close_order",
        "update_status",
        "create_confirmation",
    ])
    def test_write_tools_trigger_hitl(self, gate, tool_name):
        """All registered write tools must trigger HITL gate."""
        result = gate.check(tool_name, {"order_id": "4002310"})
        assert result is not None
        assert isinstance(result, HITLRequest)
        assert result.tool_name == tool_name

    # ─── Read Tools Pass Through ─────────────────────────────────────

    @pytest.mark.parametrize("tool_name", [
        "get_order",
        "get_costs",
        "search_orders",
        "get_equipment",
        "unknown_tool",
    ])
    def test_read_tools_do_not_trigger_hitl(self, gate, tool_name):
        """Read-only tools should never trigger HITL."""
        result = gate.check(tool_name, {"order_id": "4002310"})
        assert result is None

    # ─── Disabled Gate ───────────────────────────────────────────────

    def test_disabled_gate_allows_everything(self):
        """When HITL is disabled, even write tools pass through."""
        gate = HITLGate(enabled=False)
        result = gate.check("close_order", {"order_id": "4002310"})
        assert result is None


class TestHITLConfirmationFlow:
    """Full confirmation → execution flow."""

    @pytest.fixture
    def gate(self):
        return HITLGate(enabled=True)

    def test_confirm_pending_request(self, gate):
        """Confirming a pending request clears it and records audit."""
        gate.check("close_order", {"order_id": "4002310"})
        assert gate.pending is not None

        confirmed = gate.confirm(confirmed_by="user_123")
        assert confirmed is True
        assert gate.pending is None
        assert len(gate.audit_trail) == 1
        assert gate.audit_trail[0].confirmed is True
        assert gate.audit_trail[0].confirmed_by == "user_123"

    def test_reject_pending_request(self, gate):
        """Rejecting a pending request clears it and records audit."""
        gate.check("close_order", {"order_id": "4002310"})

        rejected = gate.reject(rejected_by="user_456")
        assert rejected is True
        assert gate.pending is None
        assert len(gate.audit_trail) == 1
        assert gate.audit_trail[0].confirmed is False

    def test_confirm_without_pending_returns_false(self, gate):
        """Confirming when nothing is pending returns False."""
        result = gate.confirm()
        assert result is False

    def test_reject_without_pending_returns_false(self, gate):
        """Rejecting when nothing is pending returns False."""
        result = gate.reject()
        assert result is False

    def test_multiple_confirmations_build_audit_trail(self, gate):
        """Each confirmation adds to the audit trail."""
        gate.check("close_order", {"order_id": "4002310"})
        gate.confirm()

        gate.check("update_status", {"order_id": "4002311", "status": "TECO"})
        gate.confirm()

        assert len(gate.audit_trail) == 2


class TestHITLUserMessage:
    """Test the user-facing confirmation message."""

    def test_message_contains_action(self):
        gate = HITLGate(enabled=True)
        request = gate.check("close_order", {"order_id": "4002310"})
        message = request.to_user_message()

        assert "Confirmation Required" in message
        assert "Close Maintenance Order" in message

    def test_message_lists_consequences(self):
        gate = HITLGate(enabled=True)
        request = gate.check("close_order", {"order_id": "4002310"})
        message = request.to_user_message()

        assert "TECO" in message
        assert "No further confirmations" in message

    def test_message_warns_irreversible(self):
        """If action is not reversible, warn the user."""
        gate = HITLGate(enabled=True, custom_write_tools={
            "delete_record": {
                "action": "Delete Record",
                "consequences": ["Record will be permanently deleted"],
                "reversible": False,
            }
        })
        request = gate.check("delete_record", {"record_id": "123"})
        message = request.to_user_message()

        assert "cannot be undone" in message


class TestHITLCustomWriteTools:
    """Test adding custom write tools at runtime."""

    def test_custom_write_tool_triggers_hitl(self):
        gate = HITLGate(enabled=True, custom_write_tools={
            "approve_purchase": {
                "action": "Approve Purchase Order",
                "consequences": ["PO will be released for procurement"],
                "reversible": True,
            }
        })

        result = gate.check("approve_purchase", {"po_id": "450001"})
        assert result is not None
        assert "Approve Purchase Order" in result.action

    def test_is_write_tool_helper(self):
        gate = HITLGate(enabled=True)
        assert gate.is_write_tool("close_order") is True
        assert gate.is_write_tool("get_order") is False
