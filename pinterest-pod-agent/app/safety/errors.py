"""Error classification for Celery task retry decisions.

Publish-job and browser-automation errors come in two flavours:

* **RetryableError** — network blips, AdsPower hiccups, API rate-limits.
  Celery may retry these with exponential backoff.
* **FatalError** — account bans, missing assets, NSFW flags.
  Celery must NOT retry these; the task is marked ``failed`` immediately.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# exception classes
# ---------------------------------------------------------------------------


class NanobotError(RuntimeError):
    """Base for all nanobot-specific errors."""


class RetryableError(NanobotError):
    """Transient error: safe to retry with backoff."""


class FatalError(NanobotError):
    """Permanent error: do NOT retry."""


# ---------------------------------------------------------------------------
# classification helpers
# ---------------------------------------------------------------------------

_FATAL_KEYWORDS = frozenset(
    {
        "forbidden", "unauthorized", "account suspended", "account banned",
        "board not found", "board_name", "no such board",
        "nsfw", "safety check", "file not found", "no such file",
        "image path does not exist", "asset missing",
    }
)

_FATAL_HTTP_STATUSES = frozenset({401, 403, 404, 410})


def classify_exception(exc: Exception) -> str:
    """Return ``"retryable"`` or ``"fatal"`` based on exception type and message.

    ``NanobotError`` subclasses are trusted directly; everything else is
    inspected via heuristic string matching against the exception message.
    """
    if isinstance(exc, FatalError):
        return "fatal"
    if isinstance(exc, RetryableError):
        return "retryable"

    # inspect wrapped exceptions
    chain = _exception_chain(exc)
    for link in chain:
        msg = str(link).lower()

        # HTTP status codes
        for status in _FATAL_HTTP_STATUSES:
            if f" {status}" in msg or f"({status})" in msg or f"[{status}]" in msg:
                return "fatal"

        # keyword heuristics
        for kw in _FATAL_KEYWORDS:
            if kw in msg:
                return "fatal"

    # Playwright timeouts / network blips → retryable
    if any("timeout" in str(link).lower() for link in chain):
        return "retryable"

    return "retryable"  # default: assume transient


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = [exc]
    current = exc
    while current.__cause__ is not None and current.__cause__ is not current:
        current = current.__cause__
        chain.append(current)
    return chain
