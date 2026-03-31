<p align="center">
  <img src="assets/agentforge-banner.png" alt="AgentForge" width="600">
  <br>
  <strong>🔥 Production-Grade Enterprise AI Agent Framework</strong>
  <br>
  <em>Build agents that survive Monday morning traffic, not just weekend demos.</em>
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Get_Started-5_min-brightgreen?style=for-the-badge" alt="Get Started"></a>
  <a href="#benchmarks"><img src="https://img.shields.io/badge/Token_Savings-78%25-blue?style=for-the-badge" alt="Token Savings"></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/Architecture-PEOS-purple?style=for-the-badge" alt="Architecture"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/LangGraph-0.2+-00ADD8?logo=data:image/svg+xml;base64,..." alt="LangGraph"></a>
  <a href="#"><img src="https://img.shields.io/badge/GPT--4o-Compatible-412991?logo=openai&logoColor=white" alt="OpenAI"></a>
  <a href="#"><img src="https://img.shields.io/badge/Anthropic-Claude-D97757?logo=anthropic&logoColor=white" alt="Anthropic"></a>
</p>

---

## 💀 The Problem

You've built a cool demo agent. It works on your laptop. Then reality hits:

```
❌ 18,000 tokens/request → $14.70 per 1K calls
❌ 12 second latency → users bounce
❌ Raw SAP errors leaking → "ABAP runtime error CX_SY_ZERODIVIDE"
❌ Agent closes a $2M maintenance order → no one asked it to
❌ Monday 9 AM: 200 concurrent users → agent hallucinates under pressure
```

**AgentForge** is what I built after hitting every one of these walls in production.

---

## ⚡ What AgentForge Does

| Feature | Naive Agent | AgentForge |
|---------|:-----------:|:----------:|
| Tokens per request | 18,400 | **4,200** (-77%) |
| Avg response time | 12.3s | **3.8s** (-69%) |
| Cost per 1K requests | $14.70 | **$3.36** (-77%) |
| Error leak rate | 8.2% | **0%** |
| Uncontrolled writes | Possible | **Impossible** (HITL gate) |
| Output consistency | Random | **Template-enforced** |

---

## 🏗️ Architecture: PEOS

**P**lanner → **E**xecutor → **O**bserver → **S**ynthesiser

```
    ┌──────────────────────────────────────────────────────────────┐
    │                      🧠 PLANNER                               │
    │  • Classifies intent from user query                         │
    │  • Selects ONLY relevant tools (dynamic binding)             │
    │  • Outputs JSON execution plan                               │
    │  • Uses 3-turn sliding window (not full history)             │
    └────────────────────────────┬─────────────────────────────────┘
                                 ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                      ⚙️ EXECUTOR                              │
    │  • Receives ONLY the tools specified in plan                 │
    │  • Loops up to N iterations (configurable)                   │
    │  • Results capped at 50KB per tool call                      │
    │  • Automatic retry with exponential backoff                  │
    └────────────────────────────┬─────────────────────────────────┘
                                 ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                      👁️ OBSERVER                              │
    │  • Validates execution completeness                          │
    │  • Checks business rules (write safety, data quality)        │
    │  • Routes to HITL gate if write operation detected           │
    │  • Can request re-execution with modified params             │
    └────────────────────────────┬─────────────────────────────────┘
                                 ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                      🎨 SYNTHESISER                           │
    │  • Applies response templates (cards, tables, markdown)      │
    │  • Generates contextual quick replies                        │
    │  • Enforces UI constraints (char limits, schema validation)  │
    │  • Zero hallucination — data-driven rendering only           │
    └──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

```bash
pip install agentforge-ai
```

```python
from agentforge import AgentForge, Tool
from agentforge.patterns import PEOS

# Define your tools
@Tool(name="get_order", description="Fetch maintenance order by ID")
async def get_order(order_id: str) -> dict:
    return await your_api.get(f"/orders/{order_id}")

@Tool(name="get_costs", description="Get cost breakdown for an order")
async def get_costs(order_id: str) -> dict:
    return await your_api.get(f"/orders/{order_id}/costs")

@Tool(name="close_order", description="Close maintenance order", write=True)
async def close_order(order_id: str, reason: str) -> dict:
    return await your_api.post(f"/orders/{order_id}/close", {"reason": reason})

# Build the agent
agent = AgentForge(
    architecture=PEOS(
        planner_model="gpt-4o-mini",      # Fast, cheap for routing
        executor_model="gpt-4o",           # Powerful for tool calling
        max_iterations=10,
        result_cap_kb=50,
    ),
    tools=[get_order, get_costs, close_order],
    hitl_enabled=True,                     # Write ops need human approval
    error_sanitization=True,               # Never leak raw errors
    response_format="enterprise_card",     # Consistent structured output
)

# Run
response = await agent.run("What's the cost breakdown for order 4002310?")
print(response.text)        # "Order 4002310 total cost: $12,450..."
print(response.card)        # Structured card JSON
print(response.quick_replies)  # ["Show operations", "Show confirmations"]
```

---

## 🎯 Seven Core Patterns

| # | Pattern | File | What It Solves |
|---|---------|------|---------------|
| 1 | **PEOS Architecture** | [patterns/peos.py](agentforge/patterns/peos.py) | Uncontrolled loops, inconsistent output |
| 2 | **Dynamic Tool Binding** | [patterns/tool_binding.py](agentforge/patterns/tool_binding.py) | 60-80% token waste from unused tool schemas |
| 3 | **History Windowing** | [patterns/history.py](agentforge/patterns/history.py) | Context window overflow in long conversations |
| 4 | **HITL Write Gate** | [patterns/hitl.py](agentforge/patterns/hitl.py) | Agents executing destructive operations |
| 5 | **Error Sanitization** | [patterns/sanitizer.py](agentforge/patterns/sanitizer.py) | Backend stack traces leaking to users |
| 6 | **Result Truncation** | [patterns/truncation.py](agentforge/patterns/truncation.py) | API responses exceeding context limits |
| 7 | **Intent Cascade** | [patterns/intent.py](agentforge/patterns/intent.py) | Paying for LLM when regex would suffice |

---

## 📊 Benchmarks

Tested with 20 enterprise API tools against real OData endpoints:

```
┌─────────────────────────┬──────────────┬──────────────┬────────────┐
│ Metric                  │ ReAct Agent  │ AgentForge   │ Savings    │
├─────────────────────────┼──────────────┼──────────────┼────────────┤
│ Tokens/request          │ 18,400       │ 4,200        │ -77%       │
│ Latency (p50)           │ 8.1s         │ 2.9s         │ -64%       │
│ Latency (p99)           │ 24.7s        │ 8.2s         │ -67%       │
│ Cost/1K requests        │ $14.70       │ $3.36        │ -77%       │
│ Tool hallucination rate │ 6.1%         │ 1.4%         │ -77%       │
│ Error exposure rate     │ 8.2%         │ 0.0%         │ -100%      │
│ Write safety violations │ 2.3%         │ 0.0%         │ -100%      │
└─────────────────────────┴──────────────┴──────────────┴────────────┘
```

<details>
<summary>How to reproduce</summary>

```bash
cd benchmarks/
python run_benchmark.py --tools 20 --requests 1000 --model gpt-4o
```
</details>

---

## 🔧 Configuration

```yaml
# agentforge.yaml
agent:
  architecture: peos
  planner:
    model: gpt-4o-mini
    temperature: 0.1
    window_size: 3            # Only last 3 turns for routing
  executor:
    model: gpt-4o
    temperature: 0.0
    max_iterations: 10
    result_cap_kb: 50
    timeout_seconds: 25
  observer:
    rules:
      - completeness_check
      - write_safety_gate
      - business_rule_validation
  synthesiser:
    format: enterprise_card
    quick_reply_max_chars: 28
    
security:
  error_sanitization: true
  hitl_for_writes: true
  allowed_write_tools: ["close_order", "update_status"]
```

---

## 📁 Project Structure

```
AgentForge/
├── agentforge/
│   ├── __init__.py
│   ├── agent.py                 # Main AgentForge class
│   ├── patterns/
│   │   ├── peos.py              # PEOS state machine
│   │   ├── tool_binding.py      # Dynamic tool selection
│   │   ├── history.py           # Sliding window management
│   │   ├── hitl.py              # Human-in-the-loop gate
│   │   ├── sanitizer.py         # Error sanitization
│   │   ├── truncation.py        # Result size management
│   │   └── intent.py            # Regex → LLM cascade
│   ├── models/
│   │   ├── plan.py              # Execution plan schema
│   │   ├── response.py          # Response models
│   │   └── tool.py              # Tool definition models
│   └── utils/
│       ├── tokens.py            # Token counting utilities
│       └── metrics.py           # Observability helpers
├── examples/
│   ├── maintenance_agent.py     # Full enterprise example
│   ├── simple_agent.py          # Minimal hello-world
│   └── multi_model_agent.py     # Different models per stage
├── benchmarks/
│   ├── run_benchmark.py
│   └── results/
├── tests/
│   ├── test_peos.py
│   ├── test_tool_binding.py
│   └── test_hitl.py
├── docs/
│   ├── patterns/
│   └── architecture.md
├── agentforge.yaml              # Default config
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 🌟 Real-World Results

> *"Deployed AgentForge in production for SAP Asset Management. Handles 1000+ daily requests with 20 OData API tools, averaging 3.8s response time at $3.36/1K requests. Zero error leaks in 6 weeks."*

---

## 🤝 Contributing

1. Fork it
2. Create your feature branch: `git checkout -b feat/amazing-pattern`
3. Commit: `git commit -m 'Add amazing pattern'`
4. Push: `git push origin feat/amazing-pattern`
5. Open a Pull Request

---

## 📜 License

MIT — use it, fork it, profit from it. A ⭐ is all I ask.

---

<p align="center">
  <strong>Built with 🔥 by <a href="https://linkedin.com/in/iamnaveenkumarb">Naveen Kumar Baskaran</a></strong>
  <br>
  <em>Senior SAP Developer & AI/ML Engineer @ SAP Labs India | PhD Candidate</em>
</p>
