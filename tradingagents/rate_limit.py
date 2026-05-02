"""Shared helpers for provider rate-limit handling."""

from __future__ import annotations

from typing import Any


def is_rate_limit_error(exc: BaseException) -> bool:
    """Return True when an SDK/LangChain exception represents HTTP 429."""
    response = getattr(exc, "response", None)
    status_code = getattr(exc, "status_code", None) or getattr(response, "status_code", None)
    if status_code == 429:
        return True

    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True

    # Last-resort fallback for non-SDK wrappers that preserve only message text.
    # This can false-positive on benign messages containing "rate limit", so
    # status code and exception class checks above remain the preferred signals.
    text = str(exc).lower()
    return "rate_limit" in text or "rate limit" in text


def retry_after_seconds(exc: BaseException) -> float | None:
    """Extract a Retry-After value from an SDK exception, when present."""
    response = getattr(exc, "response", None)
    headers: Any = getattr(response, "headers", None)
    if not headers:
        return None

    raw = None
    if hasattr(headers, "get"):
        raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None

    try:
        return max(float(raw), 0.0)
    except (TypeError, ValueError):
        return None
