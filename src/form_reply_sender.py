"""Send one guarded Google Form reply to the newest eligible inbox message."""

from __future__ import annotations

import base64
import argparse
import json
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Callable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from gmail_reader import CREDENTIALS_FILE, EXPECTED_ACCOUNT, header
from customer_email_filter import assess_customer_case_email
from config import CONFIG
from automation_logger import get_automation_logger
from gmail_selection import (
    gmail_search_query,
    initialize_activation_cutoff,
    select_one_eligible_message,
)
from send_outbox import (
    FAILED_SAFE,
    LEDGER_RECORDED,
    PENDING,
    RECONCILIATION_REQUIRED,
    SENDING,
    SENT_CONFIRMED,
    SendOutcome,
    OUTBOX_DIRECTORY,
    create_customer_reply_intent,
    mark_failed_safe,
    mark_ledger_recorded,
    mark_reconciliation_required,
    mark_send_confirmed,
    transition_intent,
    load_intent,
)
from gmail_sent_reconciliation import SentMetadataAdapter, reconcile_outbox_intent


REPLY_TOKEN_FILE = Path(__file__).resolve().parent.parent / "token_reply_sender.json"
REPLIED_IDS_FILE = Path(__file__).resolve().parent.parent / ".form_reply_replied_message_ids.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
FORM_URL = CONFIG.google_form_url
REPLY_CONTENT = f"""Dear Customer,

Thank you for reaching out to us.

To help us understand and resolve your issue quickly, please fill out the below form and provide the correct and complete details related to your concern.

Please fill out the form here:
{FORM_URL}

Please make sure that all the information provided is accurate and complete. If applicable, kindly upload the required invoice and issue/customer images along with the form.

Once we receive the submitted details, our team will review the information and contact you regarding the next steps.

Thank you for your cooperation.

Best Regards,
Customer Support Team"""


def get_reply_credentials() -> Credentials:
    """Authorize a token dedicated to this controlled send test."""
    credentials: Credentials | None = None
    if REPLY_TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(REPLY_TOKEN_FILE, SCOPES)
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
        REPLY_TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def load_replied_ids() -> set[str]:
    if not REPLIED_IDS_FILE.exists():
        return set()
    data = json.loads(REPLIED_IDS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("Reply duplicate-protection file has an invalid format.")
    return set(data)


def remember_replied_id(message_id: str, replied_ids: set[str]) -> None:
    """Record an incoming Gmail ID only after Gmail confirms the reply was sent."""
    temporary_file = REPLIED_IDS_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(sorted(replied_ids | {message_id}), indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(REPLIED_IDS_FILE)


def candidate_message(service: Resource, message_id: str) -> dict[str, str]:
    """Read only the metadata required for safe selection and in-thread reply."""
    message = service.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID", "References"],
    ).execute()
    message_headers = message.get("payload", {}).get("headers", [])
    return {
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
        "sender": parseaddr(header(message_headers, "From"))[1].strip().casefold(),
        "subject": header(message_headers, "Subject"),
        "rfc_message_id": header(message_headers, "Message-ID"),
        "references": header(message_headers, "References"),
        "snippet": message.get("snippet", ""),
        "internal_date_ms": message.get("internalDate", ""),
    }


def select_inbox_message(service: Resource, replied_ids: set[str]) -> dict[str, str] | None:
    """Select one recent eligible message from a bounded query, oldest eligible first."""
    logger = get_automation_logger()
    query = gmail_search_query(CONFIG.gmail_max_age_hours)
    print("Gmail selection started.")
    logger.info("gmail_selection_start batch_size=%s", CONFIG.gmail_batch_size)
    references = service.users().messages().list(
        userId="me", q=query, maxResults=CONFIG.gmail_batch_size
    ).execute().get("messages", [])
    candidates = [candidate_message(service, reference["id"]) for reference in references]
    summary = select_one_eligible_message(
        candidates,
        replied_ids=replied_ids,
        activation_cutoff=initialize_activation_cutoff()[0],
        max_age_hours=CONFIG.gmail_max_age_hours,
        expected_account=EXPECTED_ACCOUNT,
    )
    print(f"Gmail candidate messages found: {summary.candidates_found}")
    print(
        "Gmail selection skipped: "
        f"cutoff={summary.skipped_cutoff}, too_old={summary.skipped_too_old}, "
        f"already_replied={summary.skipped_replied}, sender={summary.skipped_sender}, "
        f"filter={summary.skipped_filter}, invalid={summary.skipped_invalid}"
    )
    logger.info(
        "gmail_selection_complete candidates=%s cutoff=%s too_old=%s replied=%s sender=%s filter=%s invalid=%s selected=%s",
        summary.candidates_found, summary.skipped_cutoff, summary.skipped_too_old,
        summary.skipped_replied, summary.skipped_sender, summary.skipped_filter,
        summary.skipped_invalid, bool(summary.selected),
    )
    if summary.selected is None:
        print("No eligible Gmail message selected.")
        return None
    if not summary.selected["sender"] or summary.selected["rfc_message_id"] in {"", "(missing)"}:
        print("No eligible Gmail message selected: selected metadata is incomplete.")
        logger.warning("gmail_selection_rejected reason=incomplete_selected_metadata")
        return None
    print("Eligible Gmail message selected (one-message-per-run limit).")
    return summary.selected


def is_safe_recipient(sender: str) -> tuple[bool, str]:
    """Reject own, Google-system, and no-reply addresses before a send."""
    domain = sender.rpartition("@")[2]
    if sender == EXPECTED_ACCOUNT.casefold():
        return False, "sender is the test account itself"
    if sender == "no-reply@accounts.google.com" or sender.startswith("no-reply@"):
        return False, "sender is a no-reply address"
    if domain in {"accounts.google.com", "google.com"}:
        return False, "sender is a Google system/security address"
    return True, ""


def reply_subject(subject: str) -> str:
    return subject if subject.casefold().startswith("re:") else f"Re: {subject}"


def build_reply(
    message: dict[str, str], outbound_message_id: str = "", operation_id: str = "", message_fingerprint: str = "", outbound_message_id_marker: str = ""
) -> dict[str, str]:
    """Build the raw MIME reply and explicitly attach it to the original thread."""
    email = EmailMessage()
    email["To"] = message["sender"]
    email["Subject"] = reply_subject(message["subject"])
    email["In-Reply-To"] = message["rfc_message_id"]
    references = message["references"]
    email["References"] = (
        f"{references} {message['rfc_message_id']}".strip()
        if references and references != "(missing)"
        else message["rfc_message_id"]
    )
    if outbound_message_id:
        email["Message-ID"] = outbound_message_id
        email["X-Customer-Case-Outbound-Message-ID"] = outbound_message_id_marker
    if operation_id:
        email["X-Customer-Case-Operation-ID"] = operation_id
    if message_fingerprint:
        email["X-Customer-Case-Message-Fingerprint"] = message_fingerprint
    email.set_content(REPLY_CONTENT)
    return {"raw": base64.urlsafe_b64encode(email.as_bytes()).decode("ascii"), "threadId": message["thread_id"]}


def send_customer_reply_with_outbox(
    service: Resource,
    message: dict[str, str],
    replied_ids: set[str],
    *,
    send_callable: Callable[[dict[str, str]], dict[str, str]] | None = None,
    ledger_callback: Callable[[str, set[str]], None] | None = None,
    outbox_directory: Path = OUTBOX_DIRECTORY,
) -> SendOutcome:
    """Send once for a PENDING intent; unresolved intents are never resent here."""
    intent = create_customer_reply_intent(
        source_message_id=message["message_id"],
        source_rfc_message_id=message["rfc_message_id"],
        source_thread_id=message["thread_id"],
        recipient=message["sender"],
        subject=reply_subject(message["subject"]),
        intended_content=REPLY_CONTENT,
        directory=outbox_directory,
    )
    operation_id = str(intent["operation_id"])
    status = str(intent["status"])
    record_ledger = ledger_callback or remember_replied_id
    if status == LEDGER_RECORDED:
        return SendOutcome(status)
    if status == SENT_CONFIRMED:
        record_ledger(message["message_id"], replied_ids)
        mark_ledger_recorded(operation_id, directory=outbox_directory)
        return SendOutcome(LEDGER_RECORDED, gmail_message_id=str(intent["gmail_message_id"]), gmail_thread_id=str(intent["gmail_thread_id"]))
    if status != PENDING:
        return SendOutcome(status)
    try:
        payload = build_reply(
            message,
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
        str(sent.get("threadId", message["thread_id"])),
        directory=outbox_directory,
    )
    record_ledger(message["message_id"], replied_ids)
    mark_ledger_recorded(operation_id, directory=outbox_directory)
    return SendOutcome(
        LEDGER_RECORDED,
        sent_now=True,
        gmail_message_id=str(confirmed["gmail_message_id"]),
        gmail_thread_id=str(confirmed["gmail_thread_id"]),
    )


def reconcile_customer_reply_with_outbox(
    message: dict[str, str],
    replied_ids: set[str],
    adapter: SentMetadataAdapter,
    automation_sender: str,
    *,
    ledger_callback: Callable[[str, set[str]], None] | None = None,
    outbox_directory: Path = OUTBOX_DIRECTORY,
) -> SendOutcome:
    """Explicit adapter-injected reconciliation; it never sends a Gmail message."""
    operation_id = f"customer_reply:v1:{message['message_id']}"
    result = reconcile_outbox_intent(
        operation_id, adapter, automation_sender, directory=outbox_directory
    )
    intent = load_intent(operation_id, outbox_directory)
    if result.state != "CONFIRMED" or intent is None:
        return SendOutcome(RECONCILIATION_REQUIRED)
    if intent["status"] == LEDGER_RECORDED:
        return SendOutcome(LEDGER_RECORDED)
    if intent["status"] != SENT_CONFIRMED:
        return SendOutcome(str(intent["status"]))
    (ledger_callback or remember_replied_id)(message["message_id"], replied_ids)
    confirmed = mark_ledger_recorded(operation_id, directory=outbox_directory)
    return SendOutcome(
        str(confirmed["status"]),
        gmail_message_id=str(confirmed["gmail_message_id"]),
        gmail_thread_id=str(confirmed["gmail_thread_id"]),
    )


def main() -> int:
    arguments = argparse.ArgumentParser(description="Reply only to eligible customer case emails.")
    arguments.add_argument(
        "--dry-run", action="store_true", help="Preview eligibility and reply details without sending email."
    )
    args = arguments.parse_args()
    try:
        _, initialized = initialize_activation_cutoff()
        if initialized:
            print("Gmail automation activation initialized in observe mode; no email was sent.")
            get_automation_logger().info("gmail_activation_initialized observe_mode=true")
            return 0
        service: Resource = build("gmail", "v1", credentials=get_reply_credentials(), cache_discovery=False)
        authenticated_email = service.users().getProfile(userId="me").execute().get("emailAddress", "(unknown)")
        if authenticated_email.casefold() != EXPECTED_ACCOUNT.casefold():
            print(f"Error: expected test account {EXPECTED_ACCOUNT}, got {authenticated_email}.")
            return 2
        replied_ids = load_replied_ids()
        message = select_inbox_message(service, replied_ids)
        if message is None:
            return 0
        safe, reason = is_safe_recipient(message["sender"])
        if not safe:
            print(f"SKIPPED — AUTOMATED/SYSTEM: {reason}.")
            return 0
        eligibility = assess_customer_case_email(
            message["sender"], message["subject"], message["snippet"]
        )
        if not eligibility.eligible:
            print(f"SKIPPED — {eligibility.category}: {eligibility.reason}.")
            return 0
        print(f"ELIGIBLE and selected for reply: {eligibility.reason}.")
        if message["message_id"] in replied_ids:
            print("Safety check blocked reply: this incoming Message ID was already replied to.")
            return 0
        subject = reply_subject(message["subject"])
        print("About to send automatic reply")
        print("-----------------------------")
        print(f"To: {message['sender']}")
        print(f"Subject: {subject}")
        if args.dry_run:
            print("DRY RUN: no email was sent.")
            return 0
        outcome = send_customer_reply_with_outbox(service, message, replied_ids)
        if outcome.status != LEDGER_RECORDED:
            print(f"Reply was not sent automatically. Outbox status: {outcome.status}.")
            return 1
        print()
        print("Reply sent successfully.")
        print(f"Message ID: {outcome.gmail_message_id or '(missing)'}")
        print(f"Thread ID: {outcome.gmail_thread_id or '(missing)'}")
        return 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
