"""
Example: Maintenance Order Agent using the full PEOS pipeline.

Demonstrates:
  - PEOS orchestration (Plan → Execute → Observe → Synthesise)
  - Dynamic tool binding per intent
  - HITL gate for write operations
  - Error sanitization for SAP OData errors
  - Result truncation for large payloads
"""

from agentforge.patterns.intent import IntentCascade, IntentPattern
from agentforge.patterns.tool_binding import DynamicToolBinder, ToolGroup
from agentforge.patterns.hitl import HITLGate
from agentforge.patterns.sanitizer import ErrorSanitizer
from agentforge.patterns.truncation import ResultTruncator
from agentforge.models.tool import tool, get_all_tools
from agentforge.models.response import AgentResponse


# ── SAP Maintenance Tools ────────────────────────────────────────

@tool(name="get_maintenance_order", group="order_detail",
      description="Fetch maintenance order header, operations, components")
def get_maintenance_order(order_id: str) -> dict:
    """Simulated SAP OData call to API_MAINTENANCEORDER."""
    return {
        "MaintenanceOrder": order_id,
        "MaintenanceOrderDesc": "Pump maintenance — bearing replacement",
        "OrderType": "PM01",
        "MaintenancePlanningPlant": "1000",
        "MaintPriority": "2",
        "MaintOrdProcessPhaseCode": "03",
        "SystemStatusText": "REL MANC PRC",
        "Operations": [
            {"Activity": "0010", "OperationDescription": "Disassemble pump housing",
             "WorkCenter": "MECH01", "PlannedWork": 4.0, "ActualWork": 3.5},
            {"Activity": "0020", "OperationDescription": "Replace bearing",
             "WorkCenter": "MECH01", "PlannedWork": 2.0, "ActualWork": 0.0},
        ],
        "Components": [
            {"Material": "BEAR-6205", "RequiredQuantity": 2, "WithdrawnQuantity": 2},
            {"Material": "SEAL-OR42", "RequiredQuantity": 4, "WithdrawnQuantity": 0},
        ],
    }


@tool(name="search_orders", group="search",
      description="Search maintenance orders with filters")
def search_orders(plant: str = "", priority: str = "", phase: str = "") -> list[dict]:
    return [
        {"MaintenanceOrder": "4002310", "OrderType": "PM01", "MaintPriority": "2"},
        {"MaintenanceOrder": "4002311", "OrderType": "PM02", "MaintPriority": "1"},
    ]


@tool(name="get_order_costs", group="costs",
      description="Fetch planned vs actual costs for a maintenance order")
def get_order_costs(order_id: str) -> dict:
    return {
        "MaintenanceOrder": order_id,
        "PlannedCost": 12500.00,
        "ActualCost": 8340.00,
        "Currency": "EUR",
        "CostVariance": -4160.00,
    }


@tool(name="close_order", group="write",
      description="Technically complete (TECO) a maintenance order")
def close_order(order_id: str) -> dict:
    return {"MaintenanceOrder": order_id, "NewStatus": "TECO", "Success": True}


# ── Configuration ────────────────────────────────────────────────

INTENTS = [
    IntentPattern(name="order_summary", regex_patterns=[
        r"\border\s+\d{7}\b", r"\bshow\s+(me\s+)?order\b", r"\bsummary\b"
    ]),
    IntentPattern(name="search", regex_patterns=[
        r"\bsearch\b", r"\bfind\b.*\borders\b", r"\boverdue\b", r"\bcritical\b"
    ]),
    IntentPattern(name="costs", regex_patterns=[
        r"\bcost\b", r"\bspend\b", r"\bbudget\b", r"\bexpense\b"
    ]),
    IntentPattern(name="close_order", regex_patterns=[
        r"\bteco\b", r"\bclose\b.*\border\b", r"\bcomplete\b.*\border\b"
    ]),
]

TOOL_GROUPS = {
    "order_summary": ToolGroup(tool_names=["get_maintenance_order"]),
    "search": ToolGroup(tool_names=["search_orders"]),
    "costs": ToolGroup(tool_names=["get_order_costs"]),
    "close_order": ToolGroup(tool_names=["close_order"]),
}

# Close is a write operation — requires human confirmation
WRITE_INTENTS = {"close_order"}


def run_agent(user_query: str):
    """Run one turn of the maintenance order agent."""
    # Components
    classifier = IntentCascade(patterns=INTENTS)
    binder = DynamicToolBinder(tools=get_all_tools(), groups=TOOL_GROUPS)
    hitl = HITLGate(require_confirmation_for=WRITE_INTENTS)
    sanitizer = ErrorSanitizer()
    truncator = ResultTruncator(max_bytes=50_000)

    print(f"\n{'═' * 60}")
    print(f"  User: {user_query}")
    print(f"{'═' * 60}")

    # ── PLAN ─────────────────────────────────────────────────────
    intent, confidence, method = classifier.classify(user_query)
    print(f"  [Planner] Intent={intent}, conf={confidence:.0%}, via={method}")

    if not intent or intent not in TOOL_GROUPS:
        print("  [Planner] Unknown intent → LLM fallback")
        return

    # ── HITL CHECK ───────────────────────────────────────────────
    if intent in WRITE_INTENTS:
        needs_confirm = hitl.check(intent, {"query": user_query})
        print(f"  [HITL] Write operation detected — confirmation required: {needs_confirm}")
        # In real agent, this pauses and waits for user confirmation
        confirmed = True  # simulated
        if not confirmed:
            print("  [HITL] User declined — aborting")
            return

    # ── EXECUTE ──────────────────────────────────────────────────
    bound_tools = binder.bind(intent)
    all_count = len(get_all_tools())
    savings = (1 - len(bound_tools) / all_count) * 100
    print(f"  [Executor] Bound {len(bound_tools)}/{all_count} tools (saved {savings:.0f}% tokens)")

    # Extract order ID from query
    import re
    order_match = re.search(r"\b([34]\d{6})\b", user_query)
    order_id = order_match.group(1) if order_match else "4002310"

    try:
        tool_fn = bound_tools[0]
        if "order_id" in tool_fn.fn.__code__.co_varnames:
            result = tool_fn.fn(order_id=order_id)
        elif "plant" in tool_fn.fn.__code__.co_varnames:
            result = tool_fn.fn(plant="1000")
        else:
            result = tool_fn.fn()
    except Exception as e:
        result = {"error": sanitizer.sanitize(e)}

    # ── OBSERVE ──────────────────────────────────────────────────
    truncated = truncator.truncate(result)
    print(f"  [Observer] Result keys: {list(truncated.keys()) if isinstance(truncated, dict) else type(truncated).__name__}")

    # ── SYNTHESISE ───────────────────────────────────────────────
    response = AgentResponse.from_tool_result(intent=intent, data=truncated)
    print(f"  [Synthesiser] Response: {len(response.parts)} parts")
    print(f"\n  Answer: {response.parts[0]}")


def main():
    queries = [
        "Show me order 4002310",
        "Search for critical orders in plant 1000",
        "What are the costs for order 4002310?",
        "TECO order 4002310",           # write — triggers HITL
        "What's the meaning of life?",  # unknown — LLM fallback
    ]
    for q in queries:
        run_agent(q)


if __name__ == "__main__":
    main()
