"""
Test Suite for AgentForge — Dynamic Tool Binding

Verifies that only the tools selected by the planner are injected 
into the executor — the #1 token optimization technique.
"""

import pytest
from agentforge.models.tool import Tool, ToolRegistry, ToolDefinition
from agentforge.patterns.tool_binding import DynamicToolBinder, ToolGroup


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def sample_tools():
    """Create 10 sample tools simulating a real enterprise agent."""

    @Tool(name="get_order", description="Fetch maintenance order by ID", category="order")
    async def get_order(order_id: str) -> dict:
        return {"order_id": order_id}

    @Tool(name="get_costs", description="Get cost breakdown", category="order")
    async def get_costs(order_id: str) -> dict:
        return {"costs": []}

    @Tool(name="get_operations", description="Get operations list", category="order")
    async def get_operations(order_id: str) -> dict:
        return {"operations": []}

    @Tool(name="get_confirmations", description="Get time confirmations", category="order")
    async def get_confirmations(order_id: str) -> dict:
        return {"confirmations": []}

    @Tool(name="get_components", description="Get material components", category="order")
    async def get_components(order_id: str) -> dict:
        return {"components": []}

    @Tool(name="search_orders", description="Search orders with filters", category="search")
    async def search_orders(plant: str = "", status: str = "") -> dict:
        return {"orders": []}

    @Tool(name="search_equipment", description="Search equipment", category="search")
    async def search_equipment(plant: str = "") -> dict:
        return {"equipment": []}

    @Tool(name="get_material_stock", description="Get stock levels", category="material")
    async def get_material_stock(material: str) -> dict:
        return {"stock": 0}

    @Tool(name="close_order", description="Close order (TECO)", category="write", write=True)
    async def close_order(order_id: str, reason: str = "") -> dict:
        return {"success": True}

    @Tool(name="update_status", description="Update order status", category="write", write=True)
    async def update_status(order_id: str, status: str) -> dict:
        return {"success": True}

    return [get_order, get_costs, get_operations, get_confirmations,
            get_components, search_orders, search_equipment,
            get_material_stock, close_order, update_status]


@pytest.fixture
def registry(sample_tools):
    """Create a populated tool registry."""
    reg = ToolRegistry()
    for tool in sample_tools:
        reg.register(tool)
    return reg


@pytest.fixture
def binder(registry):
    """Create a DynamicToolBinder with all tools registered."""
    return DynamicToolBinder(registry)


# ─── Dynamic Binding Tests ───────────────────────────────────────────

class TestDynamicToolBinding:
    """Core binding behavior — select subset, save tokens."""

    def test_bind_subset_of_tools(self, binder):
        """Only requested tools are returned."""
        bound = binder.bind(["get_order", "get_costs"])
        assert len(bound) == 2
        names = [t["function"]["name"] for t in bound]
        assert "get_order" in names
        assert "get_costs" in names
        assert "search_orders" not in names

    def test_bind_single_tool(self, binder):
        """Single tool binding works."""
        bound = binder.bind(["get_order"])
        assert len(bound) == 1
        assert bound[0]["function"]["name"] == "get_order"

    def test_bind_all_tools(self, binder, registry):
        """Binding all tools returns everything (no savings)."""
        all_names = registry.get_names()
        bound = binder.bind(all_names)
        assert len(bound) == len(all_names)

    def test_bind_empty_list(self, binder):
        """Empty plan → no tools bound."""
        bound = binder.bind([])
        assert len(bound) == 0

    def test_unknown_tool_is_skipped(self, binder):
        """Unknown tool names are gracefully skipped, not crashed."""
        bound = binder.bind(["get_order", "nonexistent_tool"])
        assert len(bound) == 1
        assert bound[0]["function"]["name"] == "get_order"

    def test_token_savings_with_2_of_10(self, binder):
        """Binding 2/10 tools = 80% savings on tool definitions."""
        bound = binder.bind(["get_order", "get_costs"])
        # 2 out of 10 = 80% savings
        savings = binder._estimate_savings(len(bound))
        assert savings == 80

    def test_token_savings_with_5_of_10(self, binder):
        """Binding 5/10 tools = 50% savings."""
        bound = binder.bind(["get_order", "get_costs", "get_operations",
                            "get_confirmations", "get_components"])
        savings = binder._estimate_savings(len(bound))
        assert savings == 50


class TestToolBindingByCategory:
    """Bind tools by category rather than individual names."""

    def test_bind_order_category(self, binder):
        """Binding 'order' category returns all order tools."""
        bound = binder.bind_by_category(["order"])
        names = [t["function"]["name"] for t in bound]
        assert "get_order" in names
        assert "get_costs" in names
        assert "get_operations" in names
        # Search and write tools should NOT be included
        assert "search_orders" not in names
        assert "close_order" not in names

    def test_bind_multiple_categories(self, binder):
        """Binding multiple categories returns union."""
        bound = binder.bind_by_category(["order", "search"])
        names = [t["function"]["name"] for t in bound]
        assert "get_order" in names
        assert "search_orders" in names
        assert "close_order" not in names  # write category excluded


class TestToolGroup:
    """Pre-defined tool groups for common intents."""

    def test_order_summary_group(self):
        tools = ToolGroup.resolve("order_summary")
        assert "get_maintenance_order" in tools
        assert "get_confirmations" in tools
        assert "get_costs" in tools

    def test_search_group(self):
        tools = ToolGroup.resolve("search")
        assert "search_orders" in tools

    def test_unknown_intent_returns_empty(self):
        tools = ToolGroup.resolve("unknown_intent")
        assert tools == []


# ─── Tool Schema Tests ───────────────────────────────────────────────

class TestToolSchema:
    """Verify tool schemas are correctly formatted for LLM consumption."""

    def test_schema_has_required_fields(self, binder):
        bound = binder.bind(["get_order"])
        schema = bound[0]
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]

    def test_schema_parameters_have_types(self, binder):
        bound = binder.bind(["get_order"])
        params = bound[0]["function"]["parameters"]["properties"]
        assert "order_id" in params
        assert params["order_id"]["type"] == "string"

    def test_write_tools_are_marked(self, registry):
        """Write tools have is_write=True for HITL detection."""
        close = registry.get("close_order")
        assert close.is_write is True

        get = registry.get("get_order")
        assert get.is_write is False
