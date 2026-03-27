"""
Example: Simple Q&A agent using AgentForge patterns.

Demonstrates:
  - IntentCascade for routing
  - DynamicToolBinder for selective binding
  - ErrorSanitizer for safe error messages
  - HistoryWindow for conversation management
"""

from agentforge.patterns.intent import IntentCascade, IntentPattern
from agentforge.patterns.tool_binding import DynamicToolBinder, ToolGroup
from agentforge.patterns.sanitizer import ErrorSanitizer
from agentforge.patterns.history import HistoryWindow
from agentforge.models.tool import tool, get_all_tools


# ── Tools ────────────────────────────────────────────────────────

@tool(name="get_weather", group="weather", description="Get current weather for a city")
def get_weather(city: str) -> dict:
    """Simulated weather lookup."""
    return {"city": city, "temp": 22, "unit": "C", "condition": "Sunny"}


@tool(name="get_forecast", group="weather", description="Get 5-day forecast")
def get_forecast(city: str, days: int = 5) -> dict:
    return {"city": city, "days": days, "forecast": ["Sunny"] * days}


@tool(name="search_news", group="news", description="Search recent news articles")
def search_news(query: str, limit: int = 5) -> list[dict]:
    return [{"title": f"News about {query}", "source": "Example", "date": "2026-01-15"}]


@tool(name="get_stock", group="finance", description="Get stock price")
def get_stock(ticker: str) -> dict:
    return {"ticker": ticker, "price": 150.25, "change": "+1.2%"}


# ── Intent patterns ─────────────────────────────────────────────

INTENTS = [
    IntentPattern(name="weather", regex_patterns=[r"\bweather\b", r"\btemperature\b", r"\bhow hot\b"]),
    IntentPattern(name="forecast", regex_patterns=[r"\bforecast\b", r"\bnext \d+ days\b"]),
    IntentPattern(name="news", regex_patterns=[r"\bnews\b", r"\bheadlines\b", r"\barticles?\b"]),
    IntentPattern(name="finance", regex_patterns=[r"\bstock\b", r"\bprice\b", r"\bticker\b"]),
]

TOOL_GROUPS = {
    "weather": ToolGroup(tool_names=["get_weather"]),
    "forecast": ToolGroup(tool_names=["get_weather", "get_forecast"]),
    "news": ToolGroup(tool_names=["search_news"]),
    "finance": ToolGroup(tool_names=["get_stock"]),
}


def main():
    # Initialize components
    classifier = IntentCascade(patterns=INTENTS)
    binder = DynamicToolBinder(tools=get_all_tools(), groups=TOOL_GROUPS)
    sanitizer = ErrorSanitizer()
    history = HistoryWindow(max_messages=20)

    # Simulate conversation
    queries = [
        "What's the weather in Berlin?",
        "Show me the 5-day forecast for Berlin",
        "Any recent news about AI agents?",
        "What's the stock price for AAPL?",
        "Tell me a joke",  # unknown intent
    ]

    for query in queries:
        print(f"\n{'─' * 50}")
        print(f"User: {query}")

        # Step 1: Classify intent
        intent, confidence, method = classifier.classify(query)
        print(f"  → Intent: {intent} (confidence={confidence:.0%}, method={method})")

        # Step 2: Bind tools
        if intent and intent in TOOL_GROUPS:
            bound = binder.bind(intent)
            all_tools = get_all_tools()
            savings = (1 - len(bound) / len(all_tools)) * 100
            print(f"  → Tools: {[t.name for t in bound]} (saved {savings:.0f}% tokens)")
        else:
            print(f"  → No tool group for intent '{intent}' — would use LLM fallback")
            continue

        # Step 3: Execute tool (simplified — real agent uses PEOS loop)
        try:
            result = bound[0].fn(city="Berlin") if intent in ("weather", "forecast") else (
                bound[0].fn(query="AI agents") if intent == "news" else
                bound[0].fn(ticker="AAPL")
            )
            print(f"  → Result: {result}")
        except Exception as e:
            safe_msg = sanitizer.sanitize(e)
            print(f"  → Error (sanitized): {safe_msg}")

        # Step 4: Track history
        history.add("user", query)
        history.add("assistant", str(result))

    print(f"\n{'─' * 50}")
    print(f"History: {len(history)} messages tracked")


if __name__ == "__main__":
    main()
