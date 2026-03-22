"""Token counting and cost estimation utilities."""

from __future__ import annotations

# Approximate tokens per character (GPT-family tokenizers)
CHARS_PER_TOKEN = 4.0

# Cost per 1M tokens (approximate, varies by model)
COST_TABLE = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def estimate_tool_tokens(tool_schemas: list[dict]) -> int:
    """Estimate tokens consumed by tool/function schemas in the prompt."""
    import json
    schema_text = json.dumps(tool_schemas, separators=(",", ":"))
    return estimate_tokens(schema_text)


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> float:
    """Estimate cost in USD for a single LLM call."""
    rates = COST_TABLE.get(model, COST_TABLE["gpt-4o"])
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def token_savings_report(
    total_tools: int,
    bound_tools: int,
    tokens_per_tool: int = 150,
) -> dict:
    """Calculate token savings from dynamic tool binding."""
    naive_tokens = total_tools * tokens_per_tool
    bound_tokens = bound_tools * tokens_per_tool
    saved = naive_tokens - bound_tokens
    pct = (saved / naive_tokens * 100) if naive_tokens > 0 else 0
    return {
        "naive_tokens": naive_tokens,
        "bound_tokens": bound_tokens,
        "saved_tokens": saved,
        "savings_pct": round(pct, 1),
    }
