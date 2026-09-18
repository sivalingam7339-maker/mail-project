"""Send one deduplicated standalone internal notification for a processed case."""

from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from gmail_reader import CREDENTIALS_FILE, EXPECTED_ACCOUNT
from config import CONFIG
from send_outbox import (
    FAILED_SAFE,
    LEDGER_RECORDED,
    PENDING,
    RECONCILIATION_REQUIRED,
    SENDING,
    SENT_CONFIRMED,
    SendOutcome,
    OUTBOX_DIRECTORY,
    create_internal_notification_intent,
    mark_failed_safe,
    mark_ledger_recorded,
    mark_reconciliation_required,
    mark_send_confirmed,
    transition_intent,
    load_intent,
)
from gmail_sent_reconciliation import SentMetadataAdapter, reconcile_outbox_intent


NOTIFICATION_RECIPIENT = CONFIG.internal_notification_recipient
TOKEN_FILE = Path(__file__).resolve().parent.parent / "token_internal_notifier.json"
LEDGER_FILE = Path(__file__).resolve().parent.parent / ".internal_notified_response_ids.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_notification_service() -> Resource:
    """Return a Gmail client authorized only for this internal notification flow."""
    credentials: Credentials | None = None
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                credentials = None
        if not credentials or not credentials.valid:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(f"OAuth client file not found: {CREDENTIALS_FILE}")
            credentials = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES).run_local_server(port=0)
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    service: Resource = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    account = service.users().getProfile(userId="me").execute().get("emailAddress", "(unknown)")
    if account.casefold() != EXPECTED_ACCOUNT.casefold():
        raise ValueError(f"Expected test account {EXPECTED_ACCOUNT}, but authenticated {account}.")
    return service


def load_notified_ids() -> set[str]:
    if not LEDGER_FILE.exists():
        return set()
    data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("Internal notification ledger has an invalid format.")
    return set(data)


def record_notified_id(response_id: str, notified_ids: set[str]) -> set[str]:
    """Persist a response ID only after Gmail accepts its internal notification."""
    updated_ids = notified_ids | {response_id}
    temporary_file = LEDGER_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(sorted(updated_ids), indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(LEDGER_FILE)
    return updated_ids


def notification_body(form_fields: dict[str, str], statuses: list[str]) -> str:
    """Create the prescribed internal email without exposing any OAuth material."""
    order_id = form_fields.get("Order ID", "").strip() or "(blank)"
    lines = [
        "New Customer Case Submitted",
        "",
        "Customer Details",
        "----------------",
        f"Order ID: {order_id}",
        f"CX Number / Customer Number: {form_fields.get('CX Number / Customer Number', '')}",
        f"Issue / Problem Description: {form_fields.get('Issue / Problem Description', '')}",
        "",
        "Form Details",
        "------------",
        f"Timestamp: {form_fields.get('Timestamp', '')}",
        f"State: {form_fields.get('State', '')}",
        f"Pincode: {form_fields.get('Pincode', '')}",
        f"Complete Address: {form_fields.get('Complete Address', '')}",
        f"Additional Remarks: {form_fields.get('Additional Remarks', '')}",
    ]
    invoice = form_fields.get("Invoice", "")
    image = form_fields.get("Customer Image / Issue Image", "")
    if invoice:
        lines.extend(["", "Invoice:", invoice])
    if image:
        lines.extend(["", "Customer Image / Issue Image:", image])
    lines.extend(["", "Case Matching Result", "--------------------", f"Cases Found: {len(statuses)}", ""])
    lines.extend(statuses if statuses else ["ORDER ID NOT FOUND IN CASES"])
    lines.extend([
        "",
        f"Result: {'MATCH FOUND' if statuses else 'NOT FOUND'}",
        "",
        "Please review the customer case and take the necessary action.",
        "",
        "Customer Support Automation",
    ])
    return "\n".join(lines)


def build_notification(
    form_fields: dict[str, str], statuses: list[str], outbound_message_id: str = "", operation_id: str = "", message_fingerprint: str = "", outbound_message_id_marker: str = ""
) -> dict[str, str]:
    """Build the standalone internal message without sending it."""
    order_id = form_fields.get("Order ID", "").strip() or "(blank)"
    email = EmailMessage()
    email["To"] = NOTIFICATION_RECIPIENT
    email["Subject"] = f"New Customer Case - {order_id}"
    if outbound_message_id:
        email["Message-ID"] = outbound_message_id
        email["X-Customer-Case-Outbound-Message-ID"] = outbound_message_id_marker
    if operation_id:
        email["X-Customer-Case-Operation-ID"] = operation_id
    if message_fingerprint:
        email["X-Customer-Case-Message-Fingerprint"] = message_fingerprint
    email.set_content(notification_body(form_fields, statuses))
    return {"raw": base64.urlsafe_b64encode(email.as_bytes()).decode("ascii")}


def send_notification(
    service: Resource, form_fields: dict[str, str], statuses: list[str]
) -> dict[str, str]:
    """Compatibility wrapper for the pre-outbox direct send interface."""
    return service.users().messages().send(userId="me", body=build_notification(form_fields, statuses)).execute()


def send_notification_with_outbox(
    service: Resource,
    form_fields: dict[str, str],
    statuses: list[str],
    response_id: str,
    *,
    send_callable: Callable[[dict[str, str]], dict[str, str]] | None = None,
    outbox_directory: Path = OUTBOX_DIRECTORY,
) -> SendOutcome:
    """Send a standalone notification once; unresolved intent states never resend."""
    order_id = form_fields.get("Order ID", "").strip() or "(blank)"
    subject = f"New Customer Case - {order_id}"
    body = notification_body(form_fields, statuses)
    intent = create_internal_notification_intent(
        response_id=response_id,
        recipient=NOTIFICATION_RECIPIENT,
        subject=subject,
        intended_content=body,
        directory=outbox_directory,
    )
    operation_id = str(intent["operation_id"])
    status = str(intent["status"])
    if status in {LEDGER_RECORDED, SENT_CONFIRMED}:
        return SendOutcome(status, gmail_message_id=str(intent["gmail_message_id"]), gmail_thread_id=str(intent["gmail_thread_id"]))
    if status != PENDING:
        return SendOutcome(status)
    try:
        payload = build_notification(
            form_fields,
            statuses,
            str(intent["outbound_rfc_message_id"]),
            operation_id,
            str(intent["message_fingerprint"]),
            str(intent["outbound_message_id_marker"]),
        )
    except (KeyError, ValueError, OSError):
        mark_failed_safe(operation_id, "local_message_build_failure", directory=outbox_directory)
        return SendOutcome(FAILED_SAFE)
    transition_intent(operation_id, SENDING, directory=outbox_directory)
    sender = send_callable or (lambda body: service.users().messages().send(userId="me", body=body).execute())
    try:
        sent = sender(payload)
    except Exception:
        mark_reconciliation_required(operation_id, "gmail_send_outcome_unknown", directory=outbox_directory)
        return SendOutcome(RECONCILIATION_REQUIRED)
    confirmed = mark_send_confirmed(
        operation_id,
        str(sent.get("id", "")),
        str(sent.get("threadId", "")),
        directory=outbox_directory,
    )
    return SendOutcome(
        SENT_CONFIRMED,
        sent_now=True,
        gmail_message_id=str(confirmed["gmail_message_id"]),
        gmail_thread_id=str(confirmed["gmail_thread_id"]),
    )


def reconcile_notification_with_outbox(
    response_id: str,
    notified_ids: set[str],
    adapter: SentMetadataAdapter,
    automation_sender: str,
    *,
    ledger_callback: Callable[[str, set[str]], set[str]] = record_notified_id,
    outbox_directory: Path = OUTBOX_DIRECTORY,
) -> tuple[SendOutcome, set[str]]:
    """Explicit adapter-injected reconciliation; it never sends a Gmail message."""
    operation_id = f"internal_notification:v1:{response_id}"
    result = reconcile_outbox_intent(
        operation_id, adapter, automation_sender, directory=outbox_directory
    )
    intent = load_intent(operation_id, outbox_directory)
    if result.state != "CONFIRMED" or intent is None:
        return SendOutcome(RECONCILIATION_REQUIRED), notified_ids
    if intent["status"] == LEDGER_RECORDED:
        return SendOutcome(LEDGER_RECORDED), notified_ids
    if intent["status"] != SENT_CONFIRMED:
        return SendOutcome(str(intent["status"])), notified_ids
    updated_ids = ledger_callback(response_id, notified_ids)
    confirmed = mark_ledger_recorded(operation_id, directory=outbox_directory)
    return SendOutcome(
        str(confirmed["status"]),
        gmail_message_id=str(confirmed["gmail_message_id"]),
        gmail_thread_id=str(confirmed["gmail_thread_id"]),
    ), updated_ids
