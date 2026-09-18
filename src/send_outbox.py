"""Local durable send-intent records and fake-metadata reconciliation helpers.

This module intentionally performs no Gmail API calls and sends no email.
"""

from __future__ import annotations

import hashlib
import json
import msvcrt
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTBOX_DIRECTORY = PROJECT_ROOT / ".send_outbox"
LOCK_FILENAME = ".send_outbox.lock"
PENDING = "PENDING"
SENDING = "SENDING"
SENT_CONFIRMED = "SENT_CONFIRMED"
LEDGER_RECORDED = "LEDGER_RECORDED"
RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
FAILED_SAFE = "FAILED_SAFE"

VALID_TRANSITIONS = {
    PENDING: {SENDING, FAILED_SAFE},
    SENDING: {SENT_CONFIRMED, RECONCILIATION_REQUIRED},
    SENT_CONFIRMED: {LEDGER_RECORDED},
    LEDGER_RECORDED: set(),
    RECONCILIATION_REQUIRED: {SENT_CONFIRMED, FAILED_SAFE},
    FAILED_SAFE: set(),
}


class OutboxLockUnavailableError(ValueError):
    """Raised when another local process is changing send-intent state."""


@dataclass(frozen=True)
class SendOutcome:
    """Non-sensitive result for a future Gmail adapter; this module never sends."""

    status: str
    sent_now: bool = False
    gmail_message_id: str = ""
    gmail_thread_id: str = ""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_text(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


def fingerprint(value: str) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def recipient_fingerprint(recipient: str) -> str:
    """Normalize an RFC address header without making display names identity data."""
    _, address = parseaddr(recipient)
    return fingerprint((address or recipient).strip().casefold())


def customer_reply_operation_id(source_message_id: str) -> str:
    if not source_message_id:
        raise ValueError("Customer reply source message ID is required.")
    return f"customer_reply:v1:{source_message_id}"


def internal_notification_operation_id(response_id: str) -> str:
    if not response_id:
        raise ValueError("Internal notification Response ID is required.")
    return f"internal_notification:v1:{response_id}"


def operation_filename(operation_id: str) -> str:
    return hashlib.sha256(operation_id.encode("utf-8")).hexdigest() + ".json"


def outbound_rfc_message_id(operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
    return f"<cca-{digest}@customer-case-automation.local>"


def outbound_message_id_marker(outbound_message_id: str) -> str:
    """Header-safe deterministic marker for the requested RFC Message-ID."""
    return hashlib.sha256(outbound_message_id.encode("utf-8")).hexdigest()


def message_fingerprint(
    recipient: str, subject: str, intended_content: str, operation_id: str
) -> str:
    return fingerprint(
        "\n".join(
            [
                f"operation={operation_id}",
                f"recipient={recipient.strip().casefold()}",
                f"subject={canonical_text(subject)}",
                f"content={intended_content.replace(chr(13), '')}",
            ]
        )
    )


def record_path(operation_id: str, directory: Path = OUTBOX_DIRECTORY) -> Path:
    return directory / operation_filename(operation_id)


@contextmanager
def outbox_lock(directory: Path = OUTBOX_DIRECTORY) -> Iterator[None]:
    """Acquire a non-blocking local Windows lock; it is not distributed."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / LOCK_FILENAME).open("a+b") as lock_file:
        lock_file.seek(0, 2)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise OutboxLockUnavailableError("Another local process currently holds the send outbox lock.") from error
        try:
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def _write_record(path: Path, record: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_record(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("operation_id"), str):
        raise ValueError("Send outbox record has an invalid format.")
    return data


def load_intent(operation_id: str, directory: Path = OUTBOX_DIRECTORY) -> dict[str, Any] | None:
    path = record_path(operation_id, directory)
    return _read_record(path) if path.exists() else None


def _new_record(
    *,
    operation_id: str,
    workflow_type: str,
    recipient: str,
    subject: str,
    intended_content: str,
    source_message_id: str = "",
    source_rfc_message_id: str = "",
    source_thread_id: str = "",
    response_id: str = "",
) -> dict[str, Any]:
    now = utc_now()
    return {
        "operation_id": operation_id,
        "workflow_type": workflow_type,
        "source_message_id": source_message_id,
        "source_rfc_message_id": source_rfc_message_id,
        "source_thread_id": source_thread_id,
        "response_id": response_id,
        "recipient_hash": recipient_fingerprint(recipient),
        "subject_hash": fingerprint(subject),
        # Used only to construct a narrowly bounded Gmail Sent fallback query.
        # Strict confirmation continues to compare the immutable hashes above.
        "reconciliation_recipient": recipient,
        "reconciliation_subject": subject,
        "message_fingerprint": message_fingerprint(recipient, subject, intended_content, operation_id),
        "outbound_rfc_message_id": outbound_rfc_message_id(operation_id),
        # Gmail may replace the RFC Message-ID in its Sent copy. New intents require
        # this value to be preserved in a dedicated custom header for reconciliation.
        "outbound_message_id_marker": outbound_message_id_marker(outbound_rfc_message_id(operation_id)),
        "requires_outbound_id_header": True,
        "created_at_utc": now,
        "status": PENDING,
        "attempt_count": 0,
        "last_attempt_at_utc": "",
        "gmail_message_id": "",
        "gmail_thread_id": "",
        "reconciliation_state": "NOT_REQUIRED",
        "error_category": "",
        "updated_at_utc": now,
        "ledger_recorded": False,
    }


def create_or_load_intent(record: dict[str, Any], directory: Path = OUTBOX_DIRECTORY) -> dict[str, Any]:
    """Persist a new PENDING intent once, or return the prior record unchanged."""
    operation_id = str(record["operation_id"])
    with outbox_lock(directory):
        path = record_path(operation_id, directory)
        if path.exists():
            return _read_record(path)
        _write_record(path, record)
        return record.copy()


def create_customer_reply_intent(
    *, source_message_id: str, source_rfc_message_id: str, source_thread_id: str,
    recipient: str, subject: str, intended_content: str, directory: Path = OUTBOX_DIRECTORY,
) -> dict[str, Any]:
    operation_id = customer_reply_operation_id(source_message_id)
    return create_or_load_intent(
        _new_record(
            operation_id=operation_id,
            workflow_type="customer_reply",
            recipient=recipient,
            subject=subject,
            intended_content=intended_content,
            source_message_id=source_message_id,
            source_rfc_message_id=source_rfc_message_id,
            source_thread_id=source_thread_id,
        ),
        directory,
    )


def create_internal_notification_intent(
    *, response_id: str, recipient: str, subject: str, intended_content: str,
    directory: Path = OUTBOX_DIRECTORY,
) -> dict[str, Any]:
    operation_id = internal_notification_operation_id(response_id)
    return create_or_load_intent(
        _new_record(
            operation_id=operation_id,
            workflow_type="internal_notification",
            recipient=recipient,
            subject=subject,
            intended_content=intended_content,
            response_id=response_id,
        ),
        directory,
    )


def create_standalone_intent(
    *,
    operation_id: str,
    workflow_type: str,
    recipient: str,
    subject: str,
    intended_content: str,
    directory: Path = OUTBOX_DIRECTORY,
) -> dict[str, Any]:
    """Create a non-customer/non-Form intent using the same durable outbox format."""
    return create_or_load_intent(
        _new_record(
            operation_id=operation_id,
            workflow_type=workflow_type,
            recipient=recipient,
            subject=subject,
            intended_content=intended_content,
        ),
        directory,
    )


def transition_intent(
    operation_id: str, status: str, *, directory: Path = OUTBOX_DIRECTORY, **updates: Any
) -> dict[str, Any]:
    """Apply a validated state update atomically; no external send occurs here."""
    with outbox_lock(directory):
        path = record_path(operation_id, directory)
        record = _read_record(path)
        current = record["status"]
        if status not in VALID_TRANSITIONS.get(current, set()):
            raise ValueError(f"Invalid send outbox transition: {current} -> {status}")
        if status == SENDING:
            record["attempt_count"] += 1
            record["last_attempt_at_utc"] = utc_now()
        record.update(updates)
        record["status"] = status
        record["updated_at_utc"] = utc_now()
        _write_record(path, record)
        return record.copy()


def mark_send_confirmed(
    operation_id: str, gmail_message_id: str, gmail_thread_id: str = "", *, directory: Path = OUTBOX_DIRECTORY
) -> dict[str, Any]:
    return transition_intent(
        operation_id,
        SENT_CONFIRMED,
        directory=directory,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
        reconciliation_state="CONFIRMED",
        error_category="",
    )


def mark_ledger_recorded(operation_id: str, *, directory: Path = OUTBOX_DIRECTORY) -> dict[str, Any]:
    return transition_intent(operation_id, LEDGER_RECORDED, directory=directory, ledger_recorded=True)


def mark_reconciliation_required(
    operation_id: str, error_category: str, *, directory: Path = OUTBOX_DIRECTORY
) -> dict[str, Any]:
    return transition_intent(
        operation_id,
        RECONCILIATION_REQUIRED,
        directory=directory,
        reconciliation_state="REQUIRED",
        error_category=error_category,
    )


def mark_failed_safe(
    operation_id: str, error_category: str, *, directory: Path = OUTBOX_DIRECTORY
) -> dict[str, Any]:
    return transition_intent(
        operation_id,
        FAILED_SAFE,
        directory=directory,
        reconciliation_state="NOT_RETRYABLE",
        error_category=error_category,
    )


def may_send(record: dict[str, Any]) -> bool:
    """Only a never-attempted PENDING intent may be sent by a future Gmail adapter."""
    return record.get("status") == PENDING


def _matches_common(record: dict[str, Any], metadata: dict[str, str], automation_sender: str) -> bool:
    expected_outbound_id = record.get("outbound_message_id_marker", "")
    preserved_outbound_id = metadata.get("outbound_message_id", "")
    # Legacy intents predate the dedicated header. They can only be confirmed through
    # all other strict, workflow-specific evidence; new intents must carry it.
    outbound_id_matches = (
        bool(expected_outbound_id) and preserved_outbound_id == expected_outbound_id
        if record.get("requires_outbound_id_header", False)
        else bool(metadata.get("message_id", ""))
    )
    return (
        recipient_fingerprint(metadata.get("from", "")) == recipient_fingerprint(automation_sender)
        and recipient_fingerprint(metadata.get("to", "")) == record["recipient_hash"]
        and fingerprint(metadata.get("subject", "")) == record["subject_hash"]
        and outbound_id_matches
        and metadata.get("operation_id", "") == record["operation_id"]
        and metadata.get("message_fingerprint", "") == record["message_fingerprint"]
    )


def customer_reply_metadata_matches(
    record: dict[str, Any], metadata: dict[str, str], automation_sender: str
) -> bool:
    return (
        record.get("workflow_type") == "customer_reply"
        and _matches_common(record, metadata, automation_sender)
        and metadata.get("thread_id", "") == record["source_thread_id"]
        and metadata.get("in_reply_to", "") == record["source_rfc_message_id"]
    )


def internal_notification_metadata_matches(
    record: dict[str, Any], metadata: dict[str, str], automation_sender: str
) -> bool:
    return record.get("workflow_type") == "internal_notification" and _matches_common(
        record, metadata, automation_sender
    )
