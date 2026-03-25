"""
Human-in-the-Loop (HITL) Gate — Prevent agents from executing destructive operations.

Write operations in enterprise systems (closing orders, changing statuses,
creating records) can have significant business impact. This module ensures
no write operation executes without explicit human confirmation.

Flow:
1. Observer detects a write tool call
2. HITL gate pauses execution
3. Returns a confirmation message to the user
4. Only proceeds when user explicitly confirms
5. Audit trail records who confirmed what and when
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HITLConfirmation:
    """Record of a HITL confirmation or rejection."""

    action: str
    tool_name: str
    parameters: dict[str, Any]
    summary: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed: bool = False
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


@dataclass
class HITLRequest:
    """Request for human confirmation before executing a write operation."""

    action: str
    summary: str
    tool_name: str
    parameters: dict[str, Any]
    consequences: list[str]
    reversible: bool

    def to_user_message(self) -> str:
        """Format as a clear user-facing confirmation request."""
        lines = [
            f"⚠️ **Confirmation Required**",
            f"",
            f"**Action:** {self.action}",
            f"**Summary:** {self.summary}",
            f"",
            f"**What will happen:**",
        ]
        for consequence in self.consequences:
            lines.append(f"  • {consequence}")

        if not self.reversible:
            lines.append("")
            lines.append("⚠️ **This action cannot be undone.**")

        lines.extend([
            "",
            "Reply **'Yes'** to confirm or **'No'** to cancel.",
        ])
        return "\n".join(lines)


class HITLGate:
    """
    Gate that prevents write operations without human confirmation.

    Maintains an audit trail of all confirmation requests and decisions.
    """

    # Tools that are classified as write operations
    WRITE_TOOLS = {
        "close_order": {
            "action": "Close Maintenance Order",
            "consequences": [
                "Order status will change to TECO (Technically Complete)",
                "No further confirmations can be posted",
                "Costs will be settled on next settlement run",
            ],
            "reversible": True,  # Can UNTECO
        },
        "update_status": {
            "action": "Update Order Status",
            "consequences": [
                "Order processing phase will change",
                "Status change may trigger notifications",
            ],
            "reversible": True,
        },
        "create_confirmation": {
            "action": "Create Time Confirmation",
            "consequences": [
                "Work hours will be recorded against the operation",
                "Capacity will be consumed",
            ],
            "reversible": True,
        },
    }

    def __init__(self, enabled: bool = True, custom_write_tools: dict | None = None):
        self.enabled = enabled
        self.write_tools = {**self.WRITE_TOOLS}
        if custom_write_tools:
            self.write_tools.update(custom_write_tools)
        self.audit_trail: list[HITLConfirmation] = []
        self.pending: HITLRequest | None = None

    def check(self, tool_name: str, parameters: dict[str, Any]) -> HITLRequest | None:
        """
        Check if a tool call requires HITL confirmation.

        Returns:
            HITLRequest if confirmation needed, None if safe to proceed
        """
        if not self.enabled:
            return None

        if tool_name not in self.write_tools:
            return None

        config = self.write_tools[tool_name]
        request = HITLRequest(
            action=config["action"],
            summary=self._build_summary(tool_name, parameters),
            tool_name=tool_name,
            parameters=parameters,
            consequences=config["consequences"],
            reversible=config.get("reversible", False),
        )

        self.pending = request
        logger.warning(f"HITL gate triggered: {tool_name} with {parameters}")
        return request

    def confirm(self, confirmed_by: str = "user") -> bool:
        """
        Confirm the pending HITL request.

        Returns True if there was a pending request that was confirmed.
        """
        if self.pending is None:
            return False

        record = HITLConfirmation(
            action=self.pending.action,
            tool_name=self.pending.tool_name,
            parameters=self.pending.parameters,
            summary=self.pending.summary,
            confirmed=True,
            confirmed_by=confirmed_by,
            confirmed_at=datetime.now(timezone.utc),
        )
        self.audit_trail.append(record)
        self.pending = None

        logger.info(f"HITL confirmed by {confirmed_by}: {record.action}")
        return True

    def reject(self, rejected_by: str = "user") -> bool:
        """Reject the pending HITL request."""
        if self.pending is None:
            return False

        record = HITLConfirmation(
            action=self.pending.action,
            tool_name=self.pending.tool_name,
            parameters=self.pending.parameters,
            summary=self.pending.summary,
            confirmed=False,
            confirmed_by=rejected_by,
            confirmed_at=datetime.now(timezone.utc),
        )
        self.audit_trail.append(record)
        self.pending = None

        logger.info(f"HITL rejected by {rejected_by}: {record.action}")
        return True

    def is_write_tool(self, tool_name: str) -> bool:
        """Check if a tool is classified as a write operation."""
        return tool_name in self.write_tools

    def _build_summary(self, tool_name: str, parameters: dict) -> str:
        """Build a human-readable summary of what the tool will do."""
        param_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
        return f"{self.write_tools[tool_name]['action']}: {param_str}"
