"""
PEOS Orchestrator — The core state machine that powers AgentForge.

Planner → Executor → Observer → Synthesiser

Each stage has a focused responsibility and clear input/output contract.
This separation enables:
- Different models per stage (cheap for planning, powerful for execution)
- Independent testing of each stage
- Clear observability (why did the agent do X?)
- Controlled iteration (Observer gates re-execution)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from agentforge.models.plan import ExecutionPlan, ObserverVerdict
from agentforge.models.response import AgentResponse

if TYPE_CHECKING:
    from agentforge.agent import AgentForge

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """You are a Planning Agent. Given a user query and conversation context,
output a JSON execution plan.

Available tools: {tool_names}

Tool categories: {tool_categories}

Output ONLY valid JSON:
{{
    "intent": "<classified_intent>",
    "confidence": <0.0-1.0>,
    "tools_needed": ["tool_1", "tool_2"],
    "parameters": {{"key": "value"}},
    "reasoning": "<one sentence justification>"
}}

Rules:
1. Select the MINIMUM tools needed to answer the query
2. Never select write tools unless the user explicitly asks to modify something
3. If the query is ambiguous, select tools for the most likely interpretation
4. confidence < 0.7 = ask for clarification instead of guessing
"""

OBSERVER_SYSTEM_PROMPT = """You are an Observer Agent. Given an execution plan and results,
determine if the response is complete and safe.

Evaluate:
1. Did all planned tools execute successfully?
2. Is the data sufficient to answer the user's original query?
3. Are there any write operations that need human confirmation?
4. Should we retry with different parameters?

Output JSON:
{{
    "pass": true/false,
    "reason": "<explanation>",
    "requires_hitl": true/false,
    "retry": true/false,
    "write_action": "<description if HITL needed>",
    "write_summary": "<what will happen if confirmed>"
}}
"""


class PEOSOrchestrator:
    """
    Orchestrates the 4-stage PEOS pipeline.

    Each stage is independently replaceable — swap the planner for a
    rule-based router, or the synthesiser for a template engine.
    """

    def __init__(self, agent: AgentForge):
        self.agent = agent
        self.config = agent.config

    async def plan(self, query: str, history: list[dict]) -> ExecutionPlan:
        """
        Stage 1: PLANNER

        Classifies intent and selects tools using a lightweight, fast model.
        Only sees tool names/descriptions, NOT full schemas (saves tokens).
        """
        tool_names = self.agent.tool_registry.get_names()
        tool_categories = self.agent.tool_registry.get_categories()

        prompt = PLANNER_SYSTEM_PROMPT.format(
            tool_names=json.dumps(tool_names),
            tool_categories=json.dumps(tool_categories),
        )

        # Use sliding window — only last N turns, not full history
        messages = [
            {"role": "system", "content": prompt},
            *history[-self.config.window_size * 2:],  # Last N user+assistant pairs
            {"role": "user", "content": query},
        ]

        response = await self._call_llm(
            model=self.config.planner_model,
            messages=messages,
            temperature=self.config.planner_temperature,
        )

        plan = ExecutionPlan.from_json(response, query=query)
        logger.info(f"Plan: intent={plan.intent} tools={plan.tools_needed}")
        return plan

    async def execute(self, plan: ExecutionPlan, tools: list[dict]) -> list[dict[str, Any]]:
        """
        Stage 2: EXECUTOR

        Runs tools from the plan. Only sees tools selected by Dynamic Binding.
        Loop up to max_iterations, exit when plan is fulfilled.
        """
        messages = [
            {"role": "system", "content": f"Execute the following plan: {plan.to_instruction()}"},
            {"role": "user", "content": plan.query},
        ]

        results = []
        for iteration in range(self.config.max_iterations):
            response = await self._call_llm_with_tools(
                model=self.config.executor_model,
                messages=messages,
                tools=tools,
                temperature=self.config.executor_temperature,
            )

            if response.tool_calls:
                for call in response.tool_calls:
                    result = await self._execute_tool(call)
                    results.append(result)
                    messages.append({"role": "tool", "content": json.dumps(result)})
            else:
                # No more tool calls — executor is done
                break

        logger.info(f"Execution complete: {len(results)} tool calls in {iteration + 1} iterations")
        return results

    async def observe(self, plan: ExecutionPlan, results: list[dict]) -> ObserverVerdict:
        """
        Stage 3: OBSERVER

        Validates completeness and safety. Gates write operations through HITL.
        """
        messages = [
            {"role": "system", "content": OBSERVER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "plan": plan.to_dict(),
                "results_summary": [
                    {"tool": r.get("tool"), "success": r.get("success"), "data_size": len(str(r))}
                    for r in results
                ],
            })},
        ]

        response = await self._call_llm(
            model=self.config.planner_model,  # Cheap model for observation
            messages=messages,
            temperature=0.0,
        )

        verdict = ObserverVerdict.from_json(response)
        logger.info(f"Observer verdict: pass={verdict.passed} hitl={verdict.requires_hitl}")
        return verdict

    async def synthesise(self, plan: ExecutionPlan, results: list[dict]) -> AgentResponse:
        """
        Stage 4: SYNTHESISER

        Formats the response for the target UI. Template-driven for consistency.
        """
        # Try template first (zero LLM cost)
        template = self._get_template(plan.intent)
        if template:
            return template.render(results, plan)

        # Fallback to LLM synthesis
        messages = [
            {"role": "system", "content": (
                "Format the following data into a clear, concise response. "
                "Include only factual data from the results. No speculation."
            )},
            {"role": "user", "content": json.dumps({
                "intent": plan.intent,
                "query": plan.query,
                "results": results,
            })},
        ]

        text = await self._call_llm(
            model=self.config.planner_model,
            messages=messages,
            temperature=0.0,
        )

        return AgentResponse(
            text=text,
            card=None,
            quick_replies=self._generate_quick_replies(plan.intent),
        )

    def _get_template(self, intent: str):
        """Get a deterministic template for an intent (if available)."""
        # Templates eliminate LLM cost for known response formats
        from agentforge.patterns.templates import TEMPLATES
        return TEMPLATES.get(intent)

    def _generate_quick_replies(self, intent: str) -> list[dict[str, str]]:
        """Generate contextual quick replies based on current intent."""
        REPLY_MAP = {
            "order_summary": [
                {"title": "Show costs", "value": "Show costs"},
                {"title": "Show operations", "value": "Show operations"},
                {"title": "Show confirmations", "value": "Show confirmations"},
            ],
            "costs": [
                {"title": "Show operations", "value": "Show operations"},
                {"title": "Back to summary", "value": "Show summary"},
            ],
        }
        replies = REPLY_MAP.get(intent, [])
        # Enforce char limit
        max_chars = self.config.quick_reply_max_chars
        return [r for r in replies if len(r["title"]) <= max_chars]

    async def _call_llm(self, model: str, messages: list, temperature: float) -> str:
        """Call LLM and return text response. Override for testing."""
        # In production, uses litellm for multi-provider support
        import litellm
        litellm.drop_params = True

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=self.config.timeout_seconds,
        )
        return response.choices[0].message.content

    async def _call_llm_with_tools(self, model: str, messages: list, tools: list, temperature: float):
        """Call LLM with tool-calling capability."""
        import litellm
        litellm.drop_params = True

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            timeout=self.config.timeout_seconds,
        )
        return response.choices[0].message

    async def _execute_tool(self, tool_call) -> dict:
        """Execute a single tool call and return the result."""
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        tool = self.agent.tool_registry.get(tool_name)
        if tool is None:
            return {"tool": tool_name, "success": False, "error": "Tool not found"}

        try:
            result = await tool.execute(**tool_args)
            # Truncate large results
            result = self.agent.truncator.truncate(result)
            return {"tool": tool_name, "success": True, "data": result}
        except Exception as e:
            sanitized = self.agent.sanitizer.sanitize(e)
            return {"tool": tool_name, "success": False, "error": sanitized}
