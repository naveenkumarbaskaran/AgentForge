"""
Dynamic Tool Binding — Only inject relevant tool schemas into the LLM context.

The #1 token optimization technique for enterprise agents with many tools.
Instead of sending ALL tool definitions (20 tools × ~500 tokens each = 10K tokens),
send only what the planner selected (2-4 tools × ~500 = 1-2K tokens).

Savings: 60-80% of tool-definition tokens per request.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from agentforge.models.tool import ToolRegistry

logger = logging.getLogger(__name__)


class DynamicToolBinder:
    """
    Binds only the tools needed for a specific execution plan.

    Example:
        If the agent has 20 tools but the planner says it only needs
        ["get_order", "get_costs"], only those 2 tool schemas are sent
        to the executor LLM — saving ~9,000 tokens per request.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def bind(self, tool_names: list[str]) -> list[dict[str, Any]]:
        """
        Select and return only the specified tools from the registry.

        Args:
            tool_names: List of tool names the planner selected

        Returns:
            List of tool schema dicts (OpenAI function-calling format)

        Raises:
            ValueError: If a requested tool doesn't exist in registry
        """
        bound = []
        for name in tool_names:
            tool = self.registry.get(name)
            if tool is None:
                logger.warning(f"Planner requested unknown tool: {name}")
                continue
            bound.append(tool.to_schema())

        token_savings = self._estimate_savings(len(bound))
        logger.info(
            f"Dynamic binding: {len(bound)}/{len(self.registry)} tools | "
            f"~{token_savings}% token savings on tool definitions"
        )

        return bound

    def bind_by_category(self, categories: list[str]) -> list[dict[str, Any]]:
        """
        Bind all tools in specified categories.

        Useful when the planner identifies a category (e.g., "confirmations")
        rather than specific tool names.
        """
        tools = self.registry.get_by_category(categories)
        return [t.to_schema() for t in tools]

    def _estimate_savings(self, bound_count: int) -> int:
        """Estimate percentage token savings vs sending all tools."""
        total = len(self.registry)
        if total == 0:
            return 0
        return int((1 - bound_count / total) * 100)


class ToolGroup:
    """
    Pre-defined groups of tools for common intents.

    Eliminates the need for the planner to enumerate individual tools —
    it can just say "order_summary" and get the right 5 tools.
    """

    GROUPS: dict[str, list[str]] = {
        "order_summary": [
            "get_maintenance_order",
            "get_confirmations",
            "get_costs",
            "get_operations",
            "get_components",
        ],
        "search": [
            "search_orders",
            "search_notifications",
            "search_equipment",
        ],
        "write_operations": [
            "close_order",
            "update_status",
            "create_confirmation",
        ],
        "material_analysis": [
            "get_material_stock",
            "get_goods_movements",
            "get_purchase_orders",
        ],
    }

    @classmethod
    def resolve(cls, intent: str) -> list[str]:
        """Resolve an intent to its tool group."""
        return cls.GROUPS.get(intent, [])
