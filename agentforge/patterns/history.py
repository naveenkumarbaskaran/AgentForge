"""
History Windowing — Prevent conversation context from growing unbounded.

Problem: Each turn adds ~500-2000 tokens. After 20 turns, you're spending
10-40K tokens just on history — before tool schemas or actual content.

Solution: Sliding window that keeps only the last N turns for the planner,
while the full history is available for reference if needed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Turn:
    """A single conversation turn (user message + assistant response)."""
    user: str
    assistant: str


class HistoryWindow:
    """
    Sliding window for conversation history management.
    
    The planner only sees the last `max_turns` exchanges.
    This provides ~70% token savings on history alone for long conversations.
    """

    def __init__(self, max_turns: int = 3, max_messages: int = 40):
        self.max_turns = max_turns
        self.max_messages = max_messages
        self._window: deque[Turn] = deque(maxlen=max_turns)
        self._full_history: list[Turn] = []

    def add_turn(self, user_message: str, assistant_response: str) -> None:
        """Add a complete turn to history."""
        turn = Turn(user=user_message, assistant=assistant_response)
        self._window.append(turn)
        self._full_history.append(turn)

    def get_window(self) -> list[dict[str, str]]:
        """
        Get the sliding window as LLM message format.
        
        Returns only last N turns — this is what the planner sees.
        """
        messages = []
        for turn in self._window:
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        return messages

    def get_full_history(self) -> list[dict[str, str]]:
        """Get full conversation history (for reference/debugging)."""
        messages = []
        for turn in self._full_history[-self.max_messages:]:
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        return messages

    @property
    def turn_count(self) -> int:
        """Total turns in the conversation."""
        return len(self._full_history)

    def clear(self) -> None:
        """Reset all history."""
        self._window.clear()
        self._full_history.clear()
