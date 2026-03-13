from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    GENERATION_ERROR = "GENERATION_ERROR"
    PROVENANCE_ERROR = "PROVENANCE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class CREError(RuntimeError):
    """Structured error with a taxonomy-aligned category."""

    def __init__(self, category: ErrorCategory, message: str):
        self.category = category
        super().__init__(f"[{category.value}] {message}")


def format_error_message(category: ErrorCategory, message: str) -> str:
    return f"[{category.value}] {message}"
