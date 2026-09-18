"""One-time STEP 24C supported-workflow validation; never runs without --confirm-send."""

from __future__ import annotations

import argparse
import base64
import hashlib
from email.message import EmailMessage
from email.utils import parseaddr

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from form_reply_sender import (
    REPLIED_IDS_FILE,
    REPLY_CONTENT,
    REPLY_TOKEN_FILE,
    SCOPES,
    load_replied_ids,
    remember_replied_id,
    reply_subject,
)
from gmail_reader import EXPECTED_ACCOUNT, header
from gmail_sent_live_adapter import create_live_readonly_adapter
from gmail_sent_reconciliation import reconcile_record
from send_outbox import (
    LEDGER_RECORDED,
    PENDING,
    RECONCILIATION_REQUIRED,
    SENDING,
    SENT_CONFIRMED,
    create_customer_reply_intent,
    load_intent,
    mark_ledger_recorded,
    mark_reconciliation_required,
    mark_send_confirmed,
    transition_intent,
)


TEST_RECIPIENT = "arthikaraj18@gmail.com"
TEST_SUBJECT = "STEP 24C FINAL TEST - Installation Support"
CONTROLLED_TEST_MARKER = "STEP 24C CONTROLLED CUSTOMER-REPLY TEST — DO NOT TREAT AS A CUSTOMER REQUEST"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def existing_send_credentials() -> Credentials:
    """Open the existing send token only; do not refresh, reauthorize, or write it."""
    if not REPLY_TOKEN_FILE.exists():
        raise FileNotFoundError("Existing customer-reply token is not available.")
    credentials = Credentials.from_authorized_user_file(REPLY_TOKEN_FILE, SCOPES)
    if not credentials.valid or not credentials.has_scopes(SCOPES):
        raise ValueError("Existing customer-reply authentication is not valid; no token change was attempted.")
    return credentials


def approved_source_message(service: Resource, replied_ids: set[str]) -> dict[str, str]:
    """Select one existing inbound message from the explicitly approved test recipient."""
    references = service.users().messages().list(
        userId="me", q=f"in:inbox from:{TEST_RECIPIENT}", maxResults=25
    ).execute().get("messages", [])
    for reference in references:
        item = service.users().messages().get(
            userId="me", id=reference["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Message-ID", "References"],
        ).execute()
        headers = item.get("payload", {}).get("headers", [])
        sender = parseaddr(header(headers, "From"))[1].strip().casefold()
        message = {
            "message_id": item.get("id", ""),
            "thread_id": item.get("threadId", ""),
            "sender": sender,
            "subject": header(headers, "Subject"),
            "rfc_message_id": header(headers, "Message-ID"),
            "references": header(headers, "References"),
        }
        if (
            sender == TEST_RECIPIENT
            and message["message_id"]
            and message["thread_id"]
            and TEST_SUBJECT in message["subject"]
            and message["rfc_message_id"]
            and message["message_id"] not in replied_ids
        ):
            return message
    raise ValueError("No unreplied inbound message from the approved test recipient was found.")


def controlled_content() -> str:
    return f"{CONTROLLED_TEST_MARKER}\n\n{REPLY_CONTENT}"


def build_controlled_reply(message: dict[str, str], intent: dict[str, object]) -> dict[str, str]:
    email = EmailMessage()
    email["To"] = TEST_RECIPIENT
    email["Subject"] = reply_subject(message["subject"])
    email["In-Reply-To"] = message["rfc_message_id"]
    email["References"] = f"{message['references']} {message['rfc_message_id']}".strip()
    email["Message-ID"] = str(intent["outbound_rfc_message_id"])
    email["X-Customer-Case-Outbound-Message-ID"] = str(intent["outbound_message_id_marker"])
    email["X-Customer-Case-Operation-ID"] = str(intent["operation_id"])
    email["X-Customer-Case-Message-Fingerprint"] = str(intent["message_fingerprint"])
    email["X-Customer-Case-Controlled-Test"] = "STEP24C"
    email.set_content(controlled_content())
    return {
        "raw": base64.urlsafe_b64encode(email.as_bytes()).decode("ascii"),
        "threadId": message["thread_id"],
    }


def print_preview(account: str, message: dict[str, str], intent: dict[str, object]) -> None:
    print(f"Authenticated account: {account}")
    print(f"Source sender: {message['sender']}")
    print(f"Recipient: {TEST_RECIPIENT}")
    print(f"Source Gmail message ID digest: {digest(message['message_id'])}")
    print(f"Source thread ID digest: {digest(message['thread_id'])}")
    print(f"Source RFC Message-ID digest: {digest(message['rfc_message_id'])}")
    print("Workflow type: customer_reply")
    print(f"Operation ID: {intent['operation_id']}")
    print(f"Message-ID digest: {digest(str(intent['outbound_rfc_message_id']))}")
    print(f"Fingerprint digest: {digest(str(intent['message_fingerprint']))}")
    print("Exactly one email will be sent only when --confirm-send is supplied.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled supported customer-reply reconciliation test.")
    parser.add_argument("--confirm-send", action="store_true", help="Explicitly permit exactly one approved test send.")
    args = parser.parse_args()

    credentials = existing_send_credentials()
    service: Resource = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    account = service.users().getProfile(userId="me").execute().get("emailAddress", "")
    if account.casefold() != EXPECTED_ACCOUNT.casefold():
        raise ValueError("Authenticated account does not match the approved TEST account.")

    replied_ids = load_replied_ids()
    message = approved_source_message(service, replied_ids)
    if message["sender"] != TEST_RECIPIENT:
        raise ValueError("Selected recipient does not match the approved external test recipient.")
    intent = create_customer_reply_intent(
        source_message_id=message["message_id"],
        source_rfc_message_id=message["rfc_message_id"],
        source_thread_id=message["thread_id"],
        recipient=TEST_RECIPIENT,
        subject=reply_subject(message["subject"]),
        intended_content=controlled_content(),
    )
    print_preview(account, message, intent)

    status = str(intent["status"])
    if not args.confirm_send:
        print("Dry run only: Gmail send and Sent reconciliation were not performed.")
        return 0
    if status == PENDING:
        payload = build_controlled_reply(message, intent)
        transition_intent(str(intent["operation_id"]), SENDING)
        try:
            sent = service.users().messages().send(userId="me", body=payload).execute()
        except Exception:
            mark_reconciliation_required(str(intent["operation_id"]), "gmail_send_outcome_unknown")
            print("Send outcome is uncertain; no resend will be attempted.")
            return 2
        intent = mark_send_confirmed(
            str(intent["operation_id"]), str(sent.get("id", "")), str(sent.get("threadId", message["thread_id"]))
        )
        print("Controlled email sent exactly once.")
    elif status not in {SENT_CONFIRMED, LEDGER_RECORDED, RECONCILIATION_REQUIRED}:
        print(f"Existing outbox state prevents sending: {status}")
        return 2

    adapter = create_live_readonly_adapter()
    current = load_intent(str(intent["operation_id"]))
    if current is None:
        raise ValueError("Outbox intent disappeared before reconciliation.")
    result = reconcile_record(current, adapter, EXPECTED_ACCOUNT)
    print(f"Sent candidates: {result.candidate_count}")
    print(f"Reconciliation result: {result.state}")
    if result.state != "CONFIRMED":
        print("No resend and no customer-ledger transition were performed.")
        return 2
    latest = load_intent(str(intent["operation_id"]))
    if latest is None:
        raise ValueError("Outbox intent disappeared after reconciliation.")
    if latest["status"] == SENT_CONFIRMED:
        remember_replied_id(message["message_id"], replied_ids)
        latest = mark_ledger_recorded(str(intent["operation_id"]))
    print(f"Outbox state: {latest['status']}")
    print("Customer ledger transition: completed after strict reconciliation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
