"""Response templates for deterministic output formatting."""

from __future__ import annotations

from typing import Any


def render_order_summary(data: dict) -> str:
    """Render a maintenance order summary as structured markdown."""
    lines = [
        f"## Order {data.get('MaintenanceOrder', 'N/A')}",
        f"**{data.get('MaintenanceOrderDesc', '')}**",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Type | {data.get('OrderType', '-')} |",
        f"| Plant | {data.get('MaintenancePlanningPlant', '-')} |",
        f"| Priority | {data.get('MaintPriority', '-')} |",
        f"| Phase | {data.get('MaintOrdProcessPhaseCode', '-')} |",
        f"| Status | {data.get('SystemStatusText', '-')} |",
    ]

    ops = data.get("Operations", [])
    if ops:
        lines.extend(["", "### Operations", "| # | Description | Work Center | Plan | Actual |",
                       "|---|-------------|-------------|------|--------|"])
        for op in ops:
            lines.append(
                f"| {op.get('Activity', '')} "
                f"| {op.get('OperationDescription', '')} "
                f"| {op.get('WorkCenter', '')} "
                f"| {op.get('PlannedWork', 0):.1f}h "
                f"| {op.get('ActualWork', 0):.1f}h |"
            )

    comps = data.get("Components", [])
    if comps:
        lines.extend(["", "### Components", "| Material | Required | Withdrawn |",
                       "|----------|----------|-----------|"])
        for c in comps:
            lines.append(
                f"| {c.get('Material', '')} "
                f"| {c.get('RequiredQuantity', 0)} "
                f"| {c.get('WithdrawnQuantity', 0)} |"
            )

    return "\n".join(lines)


def render_costs(data: dict) -> str:
    """Render cost breakdown."""
    planned = data.get("PlannedCost", 0)
    actual = data.get("ActualCost", 0)
    currency = data.get("Currency", "USD")
    variance = data.get("CostVariance", actual - planned)
    status = "🟢 Under budget" if variance < 0 else "🔴 Over budget"

    return (
        f"## Costs for Order {data.get('MaintenanceOrder', 'N/A')}\n\n"
        f"| Metric | Amount |\n|--------|--------|\n"
        f"| Planned | {planned:,.2f} {currency} |\n"
        f"| Actual | {actual:,.2f} {currency} |\n"
        f"| Variance | {variance:+,.2f} {currency} |\n"
        f"| Status | {status} |"
    )


def render_search_results(results: list[dict]) -> str:
    """Render search results as a list card."""
    if not results:
        return "No orders found matching your criteria."

    lines = [f"## Found {len(results)} Order(s)", "",
             "| Order | Type | Priority |", "|-------|------|----------|"]
    for r in results:
        lines.append(
            f"| {r.get('MaintenanceOrder', '')} "
            f"| {r.get('OrderType', '')} "
            f"| {r.get('MaintPriority', '-')} |"
        )
    return "\n".join(lines)


def quick_replies_summary(order_id: str) -> list[dict[str, str]]:
    """Quick replies after an order summary."""
    return [
        {"title": "Show confirmations", "value": f"Confirmations {order_id}"},
        {"title": "Show costs", "value": f"Costs {order_id}"},
        {"title": "Show operations", "value": f"Operations {order_id}"},
    ]


def quick_replies_drilldown(order_id: str, exclude: str = "") -> list[dict[str, str]]:
    """Quick replies after a drill-down view, cycling through other views."""
    all_qrs = [
        {"title": "Show confirmations", "value": f"Confirmations {order_id}"},
        {"title": "Show costs", "value": f"Costs {order_id}"},
        {"title": "Show operations", "value": f"Operations {order_id}"},
        {"title": "Order summary", "value": f"Order {order_id}"},
    ]
    return [qr for qr in all_qrs if exclude.lower() not in qr["title"].lower()]


TEMPLATE_REGISTRY: dict[str, Any] = {
    "order_summary": render_order_summary,
    "costs": render_costs,
    "search": render_search_results,
}
