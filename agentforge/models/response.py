"""
Agent response models — structured output for enterprise UIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResponse:
    """Structured response from the AgentForge pipeline."""

    text: str
    card: dict[str, Any] | None = None
    quick_replies: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    is_error: bool = False
    is_hitl: bool = False

    @classmethod
    def error(cls, message: str) -> AgentResponse:
        """Create an error response."""
        return cls(
            text=message,
            is_error=True,
            metadata={"error": True},
        )

    @classmethod
    def hitl_confirmation(cls, action: str, summary: str) -> AgentResponse:
        """Create a HITL confirmation request response."""
        return cls(
            text=f"⚠️ **Confirmation Required**\n\n{summary}",
            is_hitl=True,
            quick_replies=[
                {"title": "Yes, proceed", "value": f"CONFIRM:{action}"},
                {"title": "No, cancel", "value": f"REJECT:{action}"},
            ],
            metadata={"hitl_action": action},
        )

    def to_parts(self) -> list[dict]:
        """Convert to A2A protocol parts format (TextPart + DataParts)."""
        parts = [{"kind": "text", "text": self.text}]

        if self.card:
            parts.append({"kind": "data", "data": self.card})

        if self.quick_replies:
            parts.append({"kind": "data", "data": {"items": self.quick_replies}})

        return parts
