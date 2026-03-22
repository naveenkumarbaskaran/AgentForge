"""
AgentForge — Main agent orchestrator implementing the PEOS pattern.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from agentforge.models.plan import ExecutionPlan
from agentforge.models.response import AgentResponse
from agentforge.models.tool import Tool, ToolRegistry
from agentforge.patterns.hitl import HITLGate
from agentforge.patterns.history import HistoryWindow
from agentforge.patterns.intent import IntentCascade
from agentforge.patterns.peos import PEOSOrchestrator
from agentforge.patterns.sanitizer import ErrorSanitizer
from agentforge.patterns.tool_binding import DynamicToolBinder
from agentforge.patterns.truncation import ResultTruncator

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the AgentForge instance."""

    planner_model: str = "gpt-4o-mini"
    executor_model: str = "gpt-4o"
    planner_temperature: float = 0.1
    executor_temperature: float = 0.0
    max_iterations: int = 10
    result_cap_kb: int = 50
    timeout_seconds: int = 25
    window_size: int = 3
    hitl_enabled: bool = True
    error_sanitization: bool = True
    quick_reply_max_chars: int = 28
    response_format: str = "enterprise_card"


class AgentForge:
    """
    Production-grade enterprise AI agent using the PEOS architecture.

    PEOS = Planner → Executor → Observer → Synthesiser

    Key features:
    - Dynamic tool binding (60-80% token savings)
    - Intent cascade (regex first, LLM fallback)
    - HITL gate for write operations
    - Error sanitization (zero backend leaks)
    - Result truncation (50KB cap per tool)
    - History windowing (3-turn sliding window for planner)
    """

    def __init__(
        self,
        tools: list[Callable] | None = None,
        config: AgentConfig | None = None,
        intent_patterns: dict[str, list[str]] | None = None,
        **kwargs,
    ):
        self.config = config or AgentConfig(**kwargs)
        self.tool_registry = ToolRegistry()
        self.history = HistoryWindow(max_turns=self.config.window_size)
        self.sanitizer = ErrorSanitizer()
        self.truncator = ResultTruncator(max_kb=self.config.result_cap_kb)
        self.binder = DynamicToolBinder(self.tool_registry)
        self.hitl_gate = HITLGate(enabled=self.config.hitl_enabled)
        self.intent_cascade = IntentCascade(patterns=intent_patterns or {})
        self.orchestrator = PEOSOrchestrator(self)

        # Register tools
        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

        logger.info(
            f"AgentForge initialized | tools={len(self.tool_registry)} | "
            f"model={self.config.executor_model} | hitl={self.config.hitl_enabled}"
        )

    async def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResponse:
        """
        Execute a user query through the PEOS pipeline.

        Args:
            query: Natural language user query
            context: Optional context (user_id, session_id, etc.)

        Returns:
            AgentResponse with text, card data, quick replies, and metadata
        """
        start_time = time.monotonic()
        context = context or {}

        try:
            # Phase 0: Intent Cascade — try regex first, skip LLM if possible
            intent_match = self.intent_cascade.classify(query)
            if intent_match and intent_match.confidence > 0.95:
                logger.info(f"Intent resolved by regex: {intent_match.intent}")
                # Fast path — skip planner, go directly to executor with known tools
                plan = ExecutionPlan.from_intent(intent_match)
            else:
                # Phase 1: PLANNER — classify intent, select tools
                plan = await self.orchestrator.plan(query, self.history.get_window())

            # Phase 2: EXECUTOR — run tools with dynamic binding
            bound_tools = self.binder.bind(plan.tools_needed)
            results = await self.orchestrator.execute(plan, bound_tools)

            # Apply truncation to results
            results = [self.truncator.truncate(r) for r in results]

            # Phase 3: OBSERVER — validate completeness + write safety
            verdict = await self.orchestrator.observe(plan, results)

            if verdict.requires_hitl:
                # HITL gate — return confirmation request to user
                return AgentResponse.hitl_confirmation(
                    action=verdict.write_action,
                    summary=verdict.write_summary,
                )

            if verdict.retry and plan.iteration < self.config.max_iterations:
                # Re-execute with modified parameters
                plan.iteration += 1
                results = await self.orchestrator.execute(verdict.modified_plan, bound_tools)

            # Phase 4: SYNTHESISER — format response
            response = await self.orchestrator.synthesise(plan, results)

            # Record in history
            self.history.add_turn(query, response.text)

            # Metrics
            elapsed = time.monotonic() - start_time
            response.metadata["latency_ms"] = int(elapsed * 1000)
            response.metadata["tokens_used"] = response.token_count
            response.metadata["tools_bound"] = len(bound_tools)
            response.metadata["tools_available"] = len(self.tool_registry)

            logger.info(
                f"Request complete | intent={plan.intent} | "
                f"latency={elapsed:.2f}s | tokens={response.token_count}"
            )

            return response

        except Exception as e:
            # NEVER leak raw errors to user
            sanitized = self.sanitizer.sanitize(e)
            logger.error(f"Agent error (sanitized): {sanitized} | raw: {e}")
            return AgentResponse.error(sanitized)

    def add_tool(self, tool: Callable) -> None:
        """Register a new tool at runtime."""
        self.tool_registry.register(tool)

    def reset_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()

    @property
    def stats(self) -> dict:
        """Get agent runtime statistics."""
        return {
            "tools_registered": len(self.tool_registry),
            "history_turns": self.history.turn_count,
            "config": {
                "planner_model": self.config.planner_model,
                "executor_model": self.config.executor_model,
                "hitl_enabled": self.config.hitl_enabled,
                "max_iterations": self.config.max_iterations,
            },
        }
