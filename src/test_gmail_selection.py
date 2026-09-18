"""Fake-data Gmail selection tests; no Gmail connection or OAuth file is used."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gmail_selection import initialize_activation_cutoff, select_one_eligible_message


NOW = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(hours=48)


def message(
    message_id: str,
    received: datetime,
    subject: str = "Need technician for product issue",
    snippet: str = "Product is not working.",
) -> dict[str, str]:
    return {"message_id": message_id, "sender": "customer@example.com", "subject": subject, "snippet": snippet, "rfc_message_id": "<test@example.com>", "internal_date_ms": str(int(received.timestamp() * 1000))}


def main() -> int:
    historical = message("historical", CUTOFF - timedelta(seconds=1))
    too_old = message("too-old", NOW - timedelta(hours=25))
    eligible_new = message("new", NOW - timedelta(minutes=20))
    unrelated = message("unrelated", NOW - timedelta(minutes=10), "Hello", "Just checking in.")
    result = select_one_eligible_message([historical, too_old, unrelated, eligible_new], replied_ids=set(), activation_cutoff=CUTOFF, max_age_hours=24, expected_account="test@example.com", now=NOW)
    assert result.selected is eligible_new and result.skipped_cutoff == 1 and result.skipped_too_old == 1 and result.skipped_filter == 1
    result = select_one_eligible_message([eligible_new], replied_ids={"new"}, activation_cutoff=CUTOFF, max_age_hours=24, expected_account="test@example.com", now=NOW)
    assert result.selected is None and result.skipped_replied == 1
    older = message("older", NOW - timedelta(minutes=30))
    result = select_one_eligible_message([eligible_new, older], replied_ids=set(), activation_cutoff=CUTOFF, max_age_hours=24, expected_account="test@example.com", now=NOW)
    assert result.selected is older
    with tempfile.TemporaryDirectory() as directory:
        activation_path = Path(directory) / ".gmail_activation.json"
        first, created = initialize_activation_cutoff(activation_path, now=NOW)
        second, created_again = initialize_activation_cutoff(activation_path, now=NOW + timedelta(days=1))
        assert created and not created_again and first == second == NOW
    print("Gmail selection self-test passed: cutoff, age, ledger, filter, ordering, one-selection, and stable activation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
