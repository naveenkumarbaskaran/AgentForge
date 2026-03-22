"""
Execution plan and observer verdict models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionPlan:
    """Output of the Planner stage — what to execute and how."""

    intent: str
    confidence: float
    tools_needed: list[str]
    parameters: dict[str, Any]
    reasoning: str
    query: str = ""
    iteration: int = 0

    @classmethod
    def from_json(cls, json_str: str, query: str = "") -> ExecutionPlan:
        """Parse planner LLM output into an ExecutionPlan."""
        data = json.loads(json_str)
        return cls(
            intent=data.get("intent", "unknown"),
            confidence=data.get("confidence", 0.5),
            tools_needed=data.get("tools_needed", []),
            parameters=data.get("parameters", {}),
            reasoning=data.get("reasoning", ""),
            query=query,
        )

    @classmethod
    def from_intent(cls, intent_match) -> ExecutionPlan:
        """Create a plan directly from an IntentMatch (skip LLM planner)."""
        from agentforge.patterns.tool_binding import ToolGroup

        tools = ToolGroup.resolve(intent_match.intent)
        return cls(
            intent=intent_match.intent,
            confidence=intent_match.confidence,
            tools_needed=tools,
            parameters=intent_match.parameters,
            reasoning=f"Direct match via {intent_match.method}",
            query="",
        )

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "tools_needed": self.tools_needed,
            "parameters": self.parameters,
            "reasoning": self.reasoning,
        }

    def to_instruction(self) -> str:
        """Convert to a natural language instruction for the executor."""
        params_str = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return (
            f"Intent: {self.intent}. "
            f"Use tools: {', '.join(self.tools_needed)}. "
            f"Parameters: {params_str}. "
            f"Reasoning: {self.reasoning}"
        )


@dataclass
class ObserverVerdict:
    """Output of the Observer stage — pass/fail with metadata."""

    passed: bool
    reason: str
    requires_hitl: bool = False
    retry: bool = False
    write_action: str = ""
    write_summary: str = ""
    modified_plan: ExecutionPlan | None = None

    @classmethod
    def from_json(cls, json_str: str) -> ObserverVerdict:
        """Parse observer LLM output into a verdict."""
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            passed=data.get("pass", True),
            reason=data.get("reason", ""),
            requires_hitl=data.get("requires_hitl", False),
            retry=data.get("retry", False),
            write_action=data.get("write_action", ""),
            write_summary=data.get("write_summary", ""),
        )
