"""
Intent Classification Cascade — Regex first, LLM only when needed.

Why pay for an LLM call when a regex can classify "Show costs for 4002310"?

The cascade:
1. Try regex patterns → instant, free, deterministic
2. Try keyword matching → instant, free, fuzzy
3. Fall back to LLM → 200ms+, costs tokens, but handles anything

For a typical enterprise agent, 60-70% of queries match regex patterns
(because users click quick replies, which are pre-formatted).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntentMatch:
    """Result of intent classification."""
    intent: str
    confidence: float
    parameters: dict[str, Any]
    method: str  # "regex", "keyword", or "llm"


class IntentCascade:
    """
    Multi-level intent classifier that avoids LLM when possible.

    Level 1: Regex patterns (100% confidence, 0 cost, <1ms)
    Level 2: Keyword scoring (80-95% confidence, 0 cost, <1ms)
    Level 3: LLM fallback (variable confidence, costs tokens, ~500ms)
    """

    # Default patterns for common enterprise intents
    DEFAULT_PATTERNS: dict[str, list[str]] = {
        "order_summary": [
            r"\border(?:er)?\s+(?:summary|details|info|overview)\b",
            r"\bshow\s+(?:me\s+)?order\b",
            r"\bwhat(?:'s| is)\s+(?:the\s+)?(?:status|state)\s+of\s+order\b",
            r"^(?:order|maintenance order)\s+(\d{7})$",
        ],
        "costs": [
            r"\bcosts?\b",
            r"\bexpenses?\b",
            r"\bbudget|spending\b",
            r"\bhow much\b.*\border\b",
        ],
        "confirmations": [
            r"\bconfirmation", 
            r"\btime\s+(?:entry|entries|recording)\b",
            r"\bwork\s+(?:done|completed|logged)\b",
            r"\bmissing\s+conf",
        ],
        "operations": [
            r"\boperation",
            r"\bwork\s*step",
            r"\btask\s*list",
            r"\bactivit(?:y|ies)\b",
        ],
        "search": [
            r"\bsearch\b|\bfind\b|\blist\b|\bshow\s+(?:all|me)\b",
            r"\boverdue\b|\bpending\b|\bcritical\b|\bopen\b",
            r"\bhow many\b",
        ],
        "close_order": [
            r"\bclose\b.*\border\b",
            r"\bteco\b",
            r"\btechnically\s+complete\b",
            r"\bfinish\b.*\border\b",
        ],
    }

    # Pattern to extract 7-digit order IDs
    ORDER_ID_PATTERN = re.compile(r"\b([34]\d{6})\b")

    def __init__(self, patterns: dict[str, list[str]] | None = None):
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self._compiled: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()

    def classify(self, query: str) -> IntentMatch | None:
        """
        Attempt to classify the query without using an LLM.

        Returns:
            IntentMatch if classified, None if LLM fallback needed
        """
        # Level 1: Regex patterns
        match = self._regex_classify(query)
        if match:
            return match

        # Level 2: Keyword scoring
        match = self._keyword_classify(query)
        if match:
            return match

        # Level 3: Return None → caller should use LLM
        logger.info(f"Intent cascade: no match for '{query[:50]}...' → LLM fallback")
        return None

    def _regex_classify(self, query: str) -> IntentMatch | None:
        """Level 1: Exact regex matching. Highest confidence."""
        query_lower = query.lower().strip()

        for intent, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    params = self._extract_parameters(query)
                    logger.info(f"Intent cascade [regex]: {intent} (from pattern)")
                    return IntentMatch(
                        intent=intent,
                        confidence=0.98,
                        parameters=params,
                        method="regex",
                    )
        return None

    def _keyword_classify(self, query: str) -> IntentMatch | None:
        """Level 2: Keyword frequency scoring. Medium confidence."""
        query_lower = query.lower()
        scores: dict[str, int] = {}

        KEYWORDS = {
            "order_summary": ["order", "summary", "details", "overview", "show"],
            "costs": ["cost", "expense", "budget", "spend", "price", "money"],
            "confirmations": ["confirmation", "confirm", "time", "hours", "work done"],
            "operations": ["operation", "step", "task", "activity", "work step"],
            "search": ["search", "find", "list", "filter", "all", "overdue", "critical"],
            "close_order": ["close", "teco", "complete", "finish", "done"],
        }

        for intent, keywords in KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            return None

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Need at least 2 keyword hits for confidence
        if best_score < 2:
            return None

        confidence = min(0.7 + (best_score * 0.1), 0.95)
        params = self._extract_parameters(query)

        logger.info(f"Intent cascade [keyword]: {best_intent} (score={best_score})")
        return IntentMatch(
            intent=best_intent,
            confidence=confidence,
            parameters=params,
            method="keyword",
        )

    def _extract_parameters(self, query: str) -> dict[str, Any]:
        """Extract known parameter types from the query."""
        params = {}

        # Extract order ID (7-digit number starting with 3 or 4)
        order_match = self.ORDER_ID_PATTERN.search(query)
        if order_match:
            params["order_id"] = order_match.group(1)

        # Extract plant (4-digit number after "plant")
        plant_match = re.search(r"\bplant\s+(\d{4})\b", query, re.IGNORECASE)
        if plant_match:
            params["plant"] = plant_match.group(1)

        return params

    def _compile_patterns(self) -> None:
        """Pre-compile all regex patterns for performance."""
        for intent, patterns in self.patterns.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def add_pattern(self, intent: str, pattern: str) -> None:
        """Add a new pattern at runtime."""
        if intent not in self.patterns:
            self.patterns[intent] = []
            self._compiled[intent] = []
        self.patterns[intent].append(pattern)
        self._compiled[intent].append(re.compile(pattern, re.IGNORECASE))
