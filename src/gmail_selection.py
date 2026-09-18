"""Conservative, bounded Gmail candidate selection with a durable activation cutoff."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from customer_email_filter import assess_customer_case_email


ACTIVATION_FILE = Path(__file__).resolve().parent.parent / ".gmail_activation.json"


@dataclass(frozen=True)
class SelectionSummary:
    selected: dict[str, str] | None
    candidates_found: int
    skipped_cutoff: int = 0
    skipped_too_old: int = 0
    skipped_replied: int = 0
    skipped_sender: int = 0
    skipped_filter: int = 0
    skipped_invalid: int = 0


def utc_now() -> datetime:
    return datetime.now(UTC)


def initialize_activation_cutoff(
    path: Path = ACTIVATION_FILE, now: datetime | None = None
) -> tuple[datetime, bool]:
    """Create a stable one-time cutoff; never replace an existing activation time."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("activation_cutoff_utc")
        if not isinstance(value, str):
            raise ValueError("Gmail activation file has no valid activation_cutoff_utc value.")
        try:
            cutoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Gmail activation cutoff timestamp is invalid.") from error
        if cutoff.tzinfo is None:
            raise ValueError("Gmail activation cutoff timestamp must include a timezone.")
        return cutoff.astimezone(UTC), False
    cutoff = (now or utc_now()).astimezone(UTC)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"activation_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z")}) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return cutoff, True


def gmail_search_query(max_age_hours: int) -> str:
    """Return a narrow candidate query; precise age enforcement is done locally."""
    query_days = max(1, math.ceil(max_age_hours / 24))
    return f"in:inbox newer_than:{query_days}d -category:promotions -category:social -category:updates"


def sender_is_safe(sender: str, expected_account: str) -> tuple[bool, str]:
    """Reject own, Google-system, and obvious automated senders before selection."""
    sender = sender.casefold().strip()
    domain = sender.rpartition("@")[2]
    if sender == expected_account.casefold():
        return False, "own account"
    if sender == "no-reply@accounts.google.com" or sender.startswith("no-reply@"):
        return False, "no-reply sender"
    if domain in {"accounts.google.com", "google.com"}:
        return False, "Google system sender"
    return True, ""


def internal_date(message: dict[str, str]) -> datetime | None:
    """Parse Gmail internalDate milliseconds without falling back to unreliable headers."""
    try:
        return datetime.fromtimestamp(int(message["internal_date_ms"]) / 1000, tz=UTC)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def select_one_eligible_message(
    messages: Iterable[dict[str, str]],
    *,
    replied_ids: set[str],
    activation_cutoff: datetime,
    max_age_hours: int,
    expected_account: str,
    now: datetime | None = None,
    filter_message: Callable[[str, str, str], object] = assess_customer_case_email,
) -> SelectionSummary:
    """Filter a bounded batch and choose exactly one eligible message, oldest first."""
    now = (now or utc_now()).astimezone(UTC)
    cutoff = activation_cutoff.astimezone(UTC)
    oldest_allowed = now - timedelta(hours=max_age_hours)
    eligible: list[tuple[datetime, dict[str, str]]] = []
    counts = {"cutoff": 0, "too_old": 0, "replied": 0, "sender": 0, "filter": 0, "invalid": 0}
    materialized = list(messages)
    for message in materialized:
        received = internal_date(message)
        if received is None:
            counts["invalid"] += 1
            continue
        if received <= cutoff:
            counts["cutoff"] += 1
            continue
        if received < oldest_allowed:
            counts["too_old"] += 1
            continue
        message_id = message.get("message_id", "")
        if not message_id or message_id in replied_ids:
            counts["replied"] += 1
            continue
        if not message.get("sender", "") or message.get("rfc_message_id", "") in {"", "(missing)"}:
            counts["invalid"] += 1
            continue
        safe, _ = sender_is_safe(message.get("sender", ""), expected_account)
        if not safe:
            counts["sender"] += 1
            continue
        assessment = filter_message(message.get("sender", ""), message.get("subject", ""), message.get("snippet", ""))
        if not getattr(assessment, "eligible", False):
            counts["filter"] += 1
            continue
        eligible.append((received, message))
    eligible.sort(key=lambda item: item[0])
    return SelectionSummary(
        selected=eligible[0][1] if eligible else None,
        candidates_found=len(materialized),
        skipped_cutoff=counts["cutoff"],
        skipped_too_old=counts["too_old"],
        skipped_replied=counts["replied"],
        skipped_sender=counts["sender"],
        skipped_filter=counts["filter"],
        skipped_invalid=counts["invalid"],
    )
