"""
Tool model — Define, register, and manage agent tools.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A registered tool with its metadata and callable."""

    name: str
    description: str
    function: Callable
    parameters: dict[str, Any]
    category: str = "general"
    is_write: bool = False

    def to_schema(self) -> dict:
        """Convert to OpenAI function-calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [k for k, v in self.parameters.items() if not v.get("optional")],
                },
            },
        }

    async def execute(self, **kwargs) -> Any:
        """Execute the tool function."""
        if inspect.iscoroutinefunction(self.function):
            return await self.function(**kwargs)
        return self.function(**kwargs)


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: Callable | ToolDefinition) -> None:
        """Register a tool (decorated function or ToolDefinition)."""
        if isinstance(tool, ToolDefinition):
            self._tools[tool.name] = tool
        elif hasattr(tool, "_tool_meta"):
            meta = tool._tool_meta
            self._tools[meta["name"]] = ToolDefinition(
                name=meta["name"],
                description=meta["description"],
                function=tool,
                parameters=meta.get("parameters", {}),
                category=meta.get("category", "general"),
                is_write=meta.get("write", False),
            )
        else:
            raise ValueError(f"Cannot register {tool}: use @Tool decorator")

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_names(self) -> list[str]:
        """Get all tool names."""
        return list(self._tools.keys())

    def get_categories(self) -> dict[str, list[str]]:
        """Get tools grouped by category."""
        categories: dict[str, list[str]] = {}
        for tool in self._tools.values():
            categories.setdefault(tool.category, []).append(tool.name)
        return categories

    def get_by_category(self, categories: list[str]) -> list[ToolDefinition]:
        """Get all tools in specified categories."""
        return [t for t in self._tools.values() if t.category in categories]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def Tool(
    name: str,
    description: str,
    category: str = "general",
    write: bool = False,
    parameters: dict | None = None,
):
    """
    Decorator to register a function as an agent tool.

    Usage:
        @Tool(name="get_order", description="Fetch order by ID")
        async def get_order(order_id: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Auto-detect parameters from type hints if not provided
        params = parameters
        if params is None:
            params = _infer_parameters(func)

        func._tool_meta = {
            "name": name,
            "description": description,
            "category": category,
            "write": write,
            "parameters": params,
        }
        return func
    return decorator


def _infer_parameters(func: Callable) -> dict[str, dict]:
    """Infer OpenAI-style parameters from function type hints."""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    params = {}

    TYPE_MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        hint = hints.get(param_name, str)
        json_type = TYPE_MAP.get(hint, "string")
        params[param_name] = {
            "type": json_type,
            "description": f"Parameter: {param_name}",
        }
        if param.default is not inspect.Parameter.empty:
            params[param_name]["optional"] = True

    return params
