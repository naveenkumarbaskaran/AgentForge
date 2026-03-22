"""Lightweight metrics collection for agent runs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepMetric:
    """Metrics for a single PEOS step."""
    step: str  # "planner" | "executor" | "observer" | "synthesiser"
    duration_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tools_bound: int = 0
    error: str | None = None


@dataclass
class RunMetrics:
    """Aggregate metrics for a full agent run."""
    intent: str = ""
    steps: list[StepMetric] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0

    @property
    def total_duration_ms(self) -> int:
        return int((self.end_time - self.start_time) * 1000) if self.end_time else 0

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens_in + s.tokens_out for s in self.steps)

    @property
    def total_cost_estimate(self) -> float:
        from agentforge.utils.tokens import estimate_cost
        return sum(
            estimate_cost(s.tokens_in, s.tokens_out) for s in self.steps
        )

    def add_step(self, step: str, **kwargs: Any) -> None:
        self.steps.append(StepMetric(step=step, **kwargs))

    def finish(self) -> None:
        self.end_time = time.time()

    def summary(self) -> dict:
        return {
            "intent": self.intent,
            "duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.total_cost_estimate, 6),
            "steps": len(self.steps),
            "errors": [s.error for s in self.steps if s.error],
        }
