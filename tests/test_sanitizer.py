"""
Test Suite for AgentForge — Error Sanitization

Ensures raw backend errors NEVER reach end users.
"""

import pytest
from agentforge.patterns.sanitizer import ErrorSanitizer


class TestHTTPErrorMapping:
    """HTTP status codes should map to friendly messages."""

    @pytest.fixture
    def sanitizer(self):
        return ErrorSanitizer()

    @pytest.mark.parametrize("status,expected_fragment", [
        (400, "check your input"),
        (401, "Authentication failed"),
        (403, "don't have permission"),
        (404, "not found"),
        (429, "Too many requests"),
        (500, "internal service error"),
        (502, "temporarily unavailable"),
        (503, "currently overloaded"),
    ])
    def test_http_status_mapped(self, sanitizer, status, expected_fragment):
        """Each HTTP error code produces a safe, friendly message."""

        class FakeHTTPError(Exception):
            def __init__(self, code):
                self.status_code = code
                super().__init__(f"HTTP {code}")

        result = sanitizer.sanitize(FakeHTTPError(status))
        assert expected_fragment in result


class TestSensitiveDataFiltering:
    """Sensitive information must be stripped from error messages."""

    @pytest.fixture
    def sanitizer(self):
        return ErrorSanitizer()

    @pytest.mark.parametrize("raw_error", [
        "Connection failed: password=SECRET123 host=db.internal",
        "ABAP runtime error CX_SY_ZERODIVIDE in /usr/sap/ER1/DVEBMGS01",
        "API key: sk-abc123def456 expired",
        "jdbc:hdb://10.0.0.5:30015 connection refused",
        "Traceback (most recent call last): File '/usr/sap/...'",
        "Error connecting to 192.168.1.100:3306",
        "BEGIN CERTIFICATE MIIBxTCCAW...",
    ])
    def test_sensitive_errors_return_generic_message(self, sanitizer, raw_error):
        """Errors containing passwords, IPs, paths, etc. must be sanitized."""
        result = sanitizer.sanitize(Exception(raw_error))
        assert "password" not in result.lower()
        assert "api key" not in result.lower()
        assert "jdbc" not in result.lower()
        assert "192.168" not in result
        assert "/usr/sap" not in result

    def test_sap_exception_classes_sanitized(self, sanitizer):
        """SAP exception class names should be stripped."""
        result = sanitizer.sanitize(Exception("CX_SY_OPEN_SQL_DB in program"))
        assert "CX_SY" not in result


class TestSafeMessagesPassThrough:
    """Short, safe error messages can pass through."""

    @pytest.fixture
    def sanitizer(self):
        return ErrorSanitizer()

    def test_short_safe_message_passes(self, sanitizer):
        result = sanitizer.sanitize(Exception("Order not found"))
        assert "Order not found" in result

    def test_generic_fallback_for_long_messages(self, sanitizer):
        """Long messages default to generic regardless of content."""
        long_msg = "Something went wrong " * 20  # >100 chars
        result = sanitizer.sanitize(Exception(long_msg))
        assert "Something went wrong" in result  # Generic message


class TestAPIResponseSanitization:
    """Sanitize API response bodies before passing to LLM context."""

    @pytest.fixture
    def sanitizer(self):
        return ErrorSanitizer()

    def test_redacts_passwords_in_response_body(self, sanitizer):
        body = '{"error": "auth failed", "password": "secret123"}'
        result = sanitizer.sanitize_api_response(body)
        assert "[REDACTED]" in result
        assert "secret123" not in result

    def test_redacts_ip_addresses(self, sanitizer):
        body = 'Connection to 10.0.0.5:30015 failed'
        result = sanitizer.sanitize_api_response(body)
        assert "10.0.0.5" not in result

    def test_safe_body_passes_unchanged(self, sanitizer):
        body = '{"message": "Order 4002310 not found", "code": 404}'
        result = sanitizer.sanitize_api_response(body)
        assert result == body  # No sensitive content → unchanged


class TestCustomPatterns:
    """Test adding custom sensitive patterns."""

    def test_custom_pattern_detected(self):
        sanitizer = ErrorSanitizer(custom_patterns=[r"INTERNAL_PROJECT_\w+"])
        result = sanitizer.sanitize(Exception("Error in INTERNAL_PROJECT_ALPHA"))
        assert "INTERNAL_PROJECT" not in result
