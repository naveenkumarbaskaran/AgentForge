"""
Result Truncation — Cap API responses to prevent context window overflow.

Enterprise APIs (especially OData) can return massive payloads:
- 1000 items in a collection
- Deeply nested $expand results
- Verbose metadata in every response

Without truncation, a single tool result can consume 50% of the context window.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResultTruncator:
    """
    Caps tool results at a configurable size limit.
    
    Strategies:
    1. If result is a list → take first N items + "...and X more"
    2. If result is a dict → keep structure, truncate large nested values
    3. If result is a string → hard cut at char limit
    """

    def __init__(self, max_kb: int = 50, max_items: int = 50):
        self.max_bytes = max_kb * 1024
        self.max_items = max_items

    def truncate(self, result: Any) -> Any:
        """
        Truncate a tool result to stay within limits.

        Args:
            result: Raw tool result (dict, list, or string)

        Returns:
            Truncated result with metadata about what was removed
        """
        serialized = json.dumps(result) if not isinstance(result, str) else result
        
        if len(serialized.encode()) <= self.max_bytes:
            return result  # Within limits, no truncation needed

        original_size = len(serialized.encode())
        logger.warning(
            f"Truncating result: {original_size / 1024:.1f}KB → {self.max_bytes / 1024:.0f}KB"
        )

        if isinstance(result, list):
            return self._truncate_list(result, original_size)
        elif isinstance(result, dict):
            return self._truncate_dict(result, original_size)
        else:
            return self._truncate_string(str(result), original_size)

    def _truncate_list(self, items: list, original_size: int) -> dict:
        """Truncate a list by keeping first N items."""
        kept = items[:self.max_items]
        return {
            "items": kept,
            "_truncated": True,
            "_total_items": len(items),
            "_shown_items": len(kept),
            "_original_size_kb": round(original_size / 1024, 1),
        }

    def _truncate_dict(self, data: dict, original_size: int) -> dict:
        """Truncate a dict by removing large nested values."""
        result = {}
        current_size = 0

        for key, value in data.items():
            value_str = json.dumps(value)
            value_size = len(value_str.encode())

            if current_size + value_size > self.max_bytes:
                result[key] = f"[TRUNCATED: {value_size / 1024:.1f}KB]"
            else:
                result[key] = value
                current_size += value_size

        result["_truncated"] = True
        result["_original_size_kb"] = round(original_size / 1024, 1)
        return result

    def _truncate_string(self, text: str, original_size: int) -> str:
        """Hard truncation for string results."""
        max_chars = self.max_bytes  # Approximate: 1 byte per ASCII char
        truncated = text[:max_chars]
        return f"{truncated}\n\n[TRUNCATED: showing {max_chars} of {original_size} bytes]"
