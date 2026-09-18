"""One isolated, manually confirmed TEST email for outbox reconciliation validation."""

from __future__ import annotations

import argparse
import base64
import hashlib
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from gmail_reader import EXPECTED_ACCOUNT
from send_outbox import (
    PENDING,
    RECONCILIATION_REQUIRED,
    SENDING,
    SENT_CONFIRMED,
    OUTBOX_DIRECTORY,
    SendOutcome,
    create_standalone_intent,
    mark_reconciliation_required,
    mark_send_confirmed,
    message_fingerprint,
    outbound_rfc_message_id,
    transition_intent,
)


OPERATION_ID = "controlled_test_email:v1:step24c"
WORKFLOW_TYPE = "controlled_test_email"
SUBJECT = "STEP 24C CONTROLLED TEST - DO NOT REPLY"
BODY = (
    "This is a controlled internal test for the Customer Case Automation Gmail send outbox "
    "and Sent-message reconciliation.\n\nStep: 24C\n\nNo customer action is required."
)
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
REPLY_TOKEN_FILE = Path(__file__).resolve().parent.parent / "token_reply_sender.json"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def get_existing_send_credentials() -> Credentials:
    """Read the dedicated existing send token only; never refresh or write it."""
    if not REPLY_TOKEN_FILE.exists():
        raise FileNotFoundError("Existing controlled-test Gmail send token not found.")
    credentials = Credentials.from_authorized_user_file(REPLY_TOKEN_FILE, [SEND_SCOPE])
    if not credentials.valid or not credentials.has_scopes([SEND_SCOPE]):
        raise ValueError("Existing Gmail send authentication is invalid; no token change was attempted.")
    return credentials


def authenticated_account(service: Resource) -> str:
    return str(service.users().getProfile(userId="me").execute().get("emailAddress", "")).casefold()


def validate_guards(account: str, recipient: str, operation_id: str, subject: str, confirm_send: bool) -> None:
    if account != EXPECTED_ACCOUNT.casefold():
        raise ValueError("Authenticated account is not the approved TEST account.")
    if recipient.casefold() != EXPECTED_ACCOUNT.casefold():
        raise ValueError("Controlled test recipient must be the approved TEST account.")
    if operation_id != OPERATION_ID:
        raise ValueError("Controlled test operation ID is invalid.")
    if subject != SUBJECT:
        raise ValueError("Controlled test subject is invalid.")
    if not confirm_send:
        raise ValueError("--confirm-send is required; no Gmail send was attempted.")


def preview(account: str, recipient: str) -> dict[str, str]:
    """Return only non-sensitive preview values; this does not create an intent or send."""
    return {
        "account": account,
        "recipient": recipient,
        "operation_id": OPERATION_ID,
        "message_id_digest": digest(outbound_rfc_message_id(OPERATION_ID)),
        "fingerprint_digest": digest(message_fingerprint(recipient, SUBJECT, BODY, OPERATION_ID)),
    }


def build_test_message(account: str, intent: dict[str, object]) -> dict[str, str]:
    email = EmailMessage()
    email["From"] = account
    email["To"] = account
    email["Subject"] = SUBJECT
    email["Message-ID"] = str(intent["outbound_rfc_message_id"])
    email["X-Customer-Case-Operation-ID"] = OPERATION_ID
    email["X-Customer-Case-Message-Fingerprint"] = str(intent["message_fingerprint"])
    email.set_content(BODY)
    return {"raw": base64.urlsafe_b64encode(email.as_bytes()).decode("ascii")}


def run_controlled_send(
    service: Resource,
    account: str,
    *,
    confirm_send: bool,
    recipient: str = EXPECTED_ACCOUNT,
    operation_id: str = OPERATION_ID,
    subject: str = SUBJECT,
    send_callable: Callable[[dict[str, str]], dict[str, str]] | None = None,
    outbox_directory: Path = OUTBOX_DIRECTORY,
) -> SendOutcome:
    """Execute at most one confirmed test send; no application ledger is ever changed."""
    validate_guards(account, recipient, operation_id, subject, confirm_send)
    intent = create_standalone_intent(
        operation_id=operation_id,
        workflow_type=WORKFLOW_TYPE,
        recipient=recipient,
        subject=subject,
        intended_content=BODY,
        directory=outbox_directory,
    )
    status = str(intent["status"])
    if status != PENDING:
        return SendOutcome(status)
    payload = build_test_message(account, intent)
    transition_intent(operation_id, SENDING, directory=outbox_directory)
    sender = send_callable or (lambda body: service.users().messages().send(userId="me", body=body).execute())
    try:
        sent = sender(payload)
    except Exception:
        mark_reconciliation_required(operation_id, "gmail_send_outcome_unknown", directory=outbox_directory)
        return SendOutcome(RECONCILIATION_REQUIRED)
    confirmed = mark_send_confirmed(
        operation_id, str(sent.get("id", "")), str(sent.get("threadId", "")), directory=outbox_directory
    )
    return SendOutcome(
        SENT_CONFIRMED,
        sent_now=True,
        gmail_message_id=str(confirmed["gmail_message_id"]),
        gmail_thread_id=str(confirmed["gmail_thread_id"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated one-email controlled TEST send.")
    parser.add_argument("--confirm-send", action="store_true", help="Explicitly permit the one controlled self-send.")
    args = parser.parse_args()
    try:
        credentials = get_existing_send_credentials()
        service: Resource = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        account = authenticated_account(service)
        if account != EXPECTED_ACCOUNT.casefold():
            raise ValueError("Authenticated account is not the approved TEST account.")
        values = preview(account, EXPECTED_ACCOUNT)
        print(f"Authenticated account: {values['account']}")
        print(f"Recipient: {values['recipient']}")
        print(f"Subject: {SUBJECT}")
        print(f"Operation ID: {values['operation_id']}")
        print(f"Message-ID digest: {values['message_id_digest']}")
        print(f"Fingerprint digest: {values['fingerprint_digest']}")
        if not args.confirm_send:
            print("DRY RUN: --confirm-send was not supplied; Gmail send calls: 0")
            return 0
        outcome = run_controlled_send(service, account, confirm_send=True)
        if outcome.status != SENT_CONFIRMED:
            print(f"Controlled test send was not completed. Outbox status: {outcome.status}")
            return 1
        print("Controlled test email sent successfully.")
        print(f"Gmail Message ID digest: {digest(outcome.gmail_message_id)}")
        print(f"Gmail Thread ID digest: {digest(outcome.gmail_thread_id)}")
        return 0
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Controlled test blocked: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
