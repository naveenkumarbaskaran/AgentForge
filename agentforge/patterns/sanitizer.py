"""
Error Sanitization — Never leak raw backend errors to end users.

Enterprise APIs return verbose, technical error messages containing:
- Internal server paths
- Database connection strings
- Stack traces with class names
- Business object IDs that shouldn't be exposed

This module transforms raw errors into safe, user-friendly messages.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


# Patterns that indicate sensitive information
SENSITIVE_PATTERNS = [
    r"password|passwd|pwd",
    r"secret|token|api.?key",
    r"connection.?string",
    r"/usr/sap/|/SAPMNT/",
    r"ABAP.?runtime.?error",
    r"CX_[A-Z_]+",                    # SAP exception classes
    r"stack.?trace|traceback",
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP addresses
    r"jdbc:|odbc:|hdb://",            # Database connection strings
    r"BEGIN\s+CERTIFICATE",
]

# HTTP status code to user-friendly message mapping
HTTP_ERROR_MAP = {
    400: "The request couldn't be processed. Please check your input.",
    401: "Authentication failed. Please check your credentials.",
    403: "You don't have permission to access this resource.",
    404: "The requested resource was not found.",
    408: "The request timed out. Please try again.",
    429: "Too many requests. Please wait a moment and try again.",
    500: "An internal service error occurred. Please try again later.",
    502: "The service is temporarily unavailable. Please try again.",
    503: "The service is currently overloaded. Please try again later.",
    504: "The service didn't respond in time. Please try again.",
}

# Generic fallback message
GENERIC_ERROR = "Something went wrong while processing your request. Please try again."


class ErrorSanitizer:
    """
    Sanitizes errors before they reach the user or LLM context.

    Rules:
    1. Never expose raw exception messages from backend systems
    2. Map HTTP status codes to friendly messages
    3. Strip any string matching sensitive patterns
    4. Log the raw error for debugging, return sanitized for user
    """

    def __init__(self, custom_patterns: list[str] | None = None):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS]
        if custom_patterns:
            self.patterns.extend(re.compile(p, re.IGNORECASE) for p in custom_patterns)

    def sanitize(self, error: Exception) -> str:
        """
        Transform a raw exception into a safe user-facing message.

        Args:
            error: Raw exception from backend/API call

        Returns:
            Safe, user-friendly error message
        """
        raw_message = str(error)

        # Log raw for debugging
        logger.error(f"Raw error (will not reach user): {raw_message}")

        # Check if it's an HTTP error with status code
        status_code = self._extract_status_code(error)
        if status_code and status_code in HTTP_ERROR_MAP:
            return HTTP_ERROR_MAP[status_code]

        # Check if the message contains sensitive patterns
        if self._contains_sensitive(raw_message):
            return GENERIC_ERROR

        # If the message is short and seems safe, allow it through
        if len(raw_message) < 100 and not self._contains_sensitive(raw_message):
            return f"Error: {raw_message}"

        # Default: generic message
        return GENERIC_ERROR

    def sanitize_api_response(self, response_body: str) -> str:
        """
        Sanitize an API error response body before including in LLM context.

        This is for cases where error details are passed TO the LLM
        (not to the user), but we still want to strip secrets.
        """
        sanitized = response_body
        for pattern in self.patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized

    def _extract_status_code(self, error: Exception) -> int | None:
        """Try to extract HTTP status code from various exception types."""
        # requests.HTTPError
        if hasattr(error, "response") and hasattr(error.response, "status_code"):
            return error.response.status_code

        # httpx.HTTPStatusError
        if hasattr(error, "status_code"):
            return error.status_code

        # aiohttp
        if hasattr(error, "status"):
            return error.status

        # Generic: try to find status code in message
        match = re.search(r"\b([45]\d{2})\b", str(error))
        if match:
            return int(match.group(1))

        return None

    def _contains_sensitive(self, text: str) -> bool:
        """Check if text contains any sensitive patterns."""
        return any(pattern.search(text) for pattern in self.patterns)
