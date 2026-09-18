"""Small, bounded retry support for clearly transient external-service failures."""

from __future__ import annotations

import errno
import socket
import time
from collections.abc import Callable
from typing import TypeVar

from automation_logger import get_automation_logger


MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0
TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
TRANSIENT_OS_ERRORS = frozenset(
    {
        errno.ECONNABORTED,
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        errno.ETIMEDOUT,
        errno.EHOSTUNREACH,
        errno.ENETUNREACH,
    }
)
T = TypeVar("T")


def transient_error_category(error: Exception) -> str | None:
    """Return a non-sensitive category only for errors that are safe to retry."""
    response = getattr(error, "resp", None)
    status = getattr(response, "status", None) or getattr(error, "status_code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        pass
    if status in TRANSIENT_HTTP_STATUSES:
        return f"http_{status}"
    if isinstance(error, (TimeoutError, ConnectionError, socket.timeout)):
        return "network_timeout_or_connection"
    if isinstance(error, OSError) and error.errno in TRANSIENT_OS_ERRORS:
        return "network_os_error"
    if error.__class__.__name__ == "TransportError" and error.__class__.__module__.startswith("google.auth"):
        return "google_auth_transport"
    return None


def retry_call(
    operation: Callable[[], T],
    *,
    operation_name: str,
    max_attempts: int = MAX_ATTEMPTS,
    base_delay_seconds: float = BASE_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry a known-safe operation only for categorized transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    logger = get_automation_logger()
    for attempt in range(1, max_attempts + 1):
        try:
            result = operation()
            if attempt > 1:
                logger.info("retry_success operation=%s attempt=%s", operation_name, attempt)
            return result
        except Exception as error:
            category = transient_error_category(error)
            if category is None:
                logger.error("retry_not_attempted operation=%s reason=permanent_or_unknown", operation_name)
                raise
            if attempt == max_attempts:
                logger.error(
                    "retry_exhausted operation=%s attempts=%s category=%s",
                    operation_name,
                    max_attempts,
                    category,
                )
                raise
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "retry_scheduled operation=%s next_attempt=%s category=%s delay_seconds=%s",
                operation_name,
                attempt + 1,
                category,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")
