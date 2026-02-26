"""Custom exceptions for YAML test-case ingestion."""

from __future__ import annotations


class TestCaseError(Exception):
    """Base exception for YAML test-case processing."""


class TestCaseNotFoundError(TestCaseError):
    """Raised when a requested case ID cannot be found."""


class TestCaseValidationError(TestCaseError):
    """Raised when YAML payload or semantics fail validation."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(self._render())

    def _render(self) -> str:
        parts = []
        for error in self.errors:
            code = error.get("code", "validation_error")
            path = error.get("path", "<root>")
            message = error.get("message", "Invalid value")
            hint = error.get("hint")
            text = f"[{code}] {path}: {message}"
            if hint:
                text += f" (hint: {hint})"
            parts.append(text)
        return "; ".join(parts) if parts else "Validation failed"

