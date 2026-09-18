"""Strict Gmail Sent metadata reconciliation through an injected adapter.

This module contains no Gmail API client initialization and never sends email.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from send_outbox import (
    LEDGER_RECORDED,
    RECONCILIATION_REQUIRED,
    SENT_CONFIRMED,
    OUTBOX_DIRECTORY,
    customer_reply_metadata_matches,
    internal_notification_metadata_matches,
    load_intent,
    mark_send_confirmed,
)


CONFIRMED = "CONFIRMED"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"
MISMATCH = "MISMATCH"
INVALID_METADATA = "INVALID_METADATA"


class SentMetadataAdapter(Protocol):
    """Minimal future Gmail Sent adapter contract; fake implementations are used in Step 23D."""

    def find_sent_messages_by_message_id(self, outbound_message_id: str) -> list[dict[str, str]]: ...

    def find_sent_messages_for_record(self, record: dict[str, object]) -> list[dict[str, str]]: ...


@dataclass(frozen=True)
class ReconciliationResult:
    state: str
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    candidate_count: int = 0


class FakeSentMetadataAdapter:
    """Deterministic local adapter for tests; it performs no network activity."""

    def __init__(self, candidates: list[dict[str, str]]) -> None:
        self.candidates = candidates
        self.search_count = 0

    def find_sent_messages_by_message_id(self, outbound_message_id: str) -> list[dict[str, str]]:
        self.search_count += 1
        # Test fixtures represent the adapter's search result set, including noisy candidates.
        return [item.copy() for item in self.candidates]

    def find_sent_messages_for_record(self, record: dict[str, object]) -> list[dict[str, str]]:
        return self.find_sent_messages_by_message_id(str(record["outbound_rfc_message_id"]))


def _record_is_valid(record: dict[str, object]) -> bool:
    common = ("operation_id", "workflow_type", "recipient_hash", "subject_hash", "message_fingerprint", "outbound_rfc_message_id")
    if any(not isinstance(record.get(key), str) or not record[key] for key in common):
        return False
    if record["workflow_type"] == "customer_reply":
        return bool(record.get("source_thread_id") and record.get("source_rfc_message_id"))
    return record["workflow_type"] == "internal_notification"


def _candidate_has_required_metadata(candidate: dict[str, str], workflow_type: str) -> bool:
    common = ("from", "to", "subject", "message_id", "operation_id", "message_fingerprint")
    if any(not candidate.get(key) for key in common):
        return False
    if workflow_type == "customer_reply":
        return bool(candidate.get("thread_id") and candidate.get("in_reply_to"))
    return True


def reconcile_record(
    record: dict[str, object], adapter: SentMetadataAdapter, automation_sender: str
) -> ReconciliationResult:
    """Evaluate Sent metadata; no state changes or external calls beyond the injected adapter."""
    if not _record_is_valid(record):
        return ReconciliationResult(INVALID_METADATA)
    outbound_id = str(record["outbound_rfc_message_id"])
    discovery = getattr(adapter, "find_sent_messages_for_record", None)
    candidates = discovery(record) if callable(discovery) else adapter.find_sent_messages_by_message_id(outbound_id)
    if not candidates:
        return ReconciliationResult(NOT_FOUND)
    matching: list[dict[str, str]] = []
    invalid_candidate = False
    for candidate in candidates:
        if not _candidate_has_required_metadata(candidate, str(record["workflow_type"])):
            invalid_candidate = True
            continue
        if record["workflow_type"] == "customer_reply":
            matched = customer_reply_metadata_matches(record, candidate, automation_sender)  # type: ignore[arg-type]
        else:
            matched = internal_notification_metadata_matches(record, candidate, automation_sender)  # type: ignore[arg-type]
        if matched:
            matching.append(candidate)
    if len(matching) == 1:
        candidate = matching[0]
        return ReconciliationResult(
            CONFIRMED,
            gmail_message_id=candidate.get("gmail_message_id", ""),
            gmail_thread_id=candidate.get("thread_id", ""),
            candidate_count=len(candidates),
        )
    if len(matching) > 1:
        return ReconciliationResult(AMBIGUOUS, candidate_count=len(candidates))
    return ReconciliationResult(INVALID_METADATA if invalid_candidate else MISMATCH, candidate_count=len(candidates))


def reconcile_outbox_intent(
    operation_id: str,
    adapter: SentMetadataAdapter,
    automation_sender: str,
    *,
    directory: Path = OUTBOX_DIRECTORY,
) -> ReconciliationResult:
    """Confirm only exact RECONCILIATION_REQUIRED evidence; never make an intent sendable."""
    record = load_intent(operation_id, directory)
    if record is None:
        return ReconciliationResult(INVALID_METADATA)
    if record["status"] in {SENT_CONFIRMED, LEDGER_RECORDED}:
        return ReconciliationResult(
            CONFIRMED,
            gmail_message_id=str(record["gmail_message_id"]),
            gmail_thread_id=str(record["gmail_thread_id"]),
        )
    if record["status"] != RECONCILIATION_REQUIRED:
        return ReconciliationResult(INVALID_METADATA)
    result = reconcile_record(record, adapter, automation_sender)
    if result.state == CONFIRMED:
        mark_send_confirmed(
            operation_id,
            result.gmail_message_id,
            result.gmail_thread_id,
            directory=directory,
        )
    return result
