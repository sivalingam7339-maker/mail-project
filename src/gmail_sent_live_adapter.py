"""Read-only Gmail Sent metadata adapter; live access requires an explicit CLI flag."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from gmail_reader import EXPECTED_ACCOUNT, TOKEN_FILE, header
from gmail_sent_reconciliation import ReconciliationResult, SentMetadataAdapter, reconcile_record
from send_outbox import OUTBOX_DIRECTORY, fingerprint, load_intent, recipient_fingerprint


READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MESSAGE_ID_PATTERN = re.compile(r"^<[^<>\s@]+@[^<>\s@]+>$")


class ReadOnlyGmailService(Protocol):
    def users(self) -> object: ...


def validate_outbound_message_id(message_id: str) -> str:
    if not MESSAGE_ID_PATTERN.fullmatch(message_id):
        raise ValueError("A deterministic RFC Message-ID in angle brackets is required.")
    return message_id


def get_existing_readonly_credentials() -> Credentials:
    """Read the existing Gmail token only; never refresh, write, or reauthorize it."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Existing Gmail read-only token not found: {TOKEN_FILE}")
    credentials = Credentials.from_authorized_user_file(TOKEN_FILE, [READONLY_SCOPE])
    if not credentials.valid or not credentials.has_scopes([READONLY_SCOPE]):
        raise ValueError("Existing Gmail read-only authentication is not valid; no token change was attempted.")
    return credentials


class GmailSentLiveAdapter:
    """Reads only Gmail Sent metadata via list/get; it has no send or modify method."""

    def __init__(self, service: Resource) -> None:
        self._service = service

    _METADATA_HEADERS = [
        "From", "To", "Subject", "Message-ID", "In-Reply-To",
        "X-Customer-Case-Operation-ID", "X-Customer-Case-Message-Fingerprint",
        "X-Customer-Case-Outbound-Message-ID",
    ]

    def _metadata(self, reference: dict[str, str]) -> dict[str, str]:
        message = self._service.users().messages().get(
            userId="me", id=reference["id"], format="metadata", metadataHeaders=self._METADATA_HEADERS,
        ).execute()
        headers = message.get("payload", {}).get("headers", [])
        return {
            "gmail_message_id": message.get("id", ""), "thread_id": message.get("threadId", ""),
            "from": header(headers, "From"), "to": header(headers, "To"),
            "subject": header(headers, "Subject"), "message_id": header(headers, "Message-ID"),
            "operation_id": header(headers, "X-Customer-Case-Operation-ID"),
            "message_fingerprint": header(headers, "X-Customer-Case-Message-Fingerprint"),
            "outbound_message_id": header(headers, "X-Customer-Case-Outbound-Message-ID"),
            "in_reply_to": header(headers, "In-Reply-To"),
        }

    def _list_metadata(self, query: str) -> list[dict[str, str]]:
        references = self._service.users().messages().list(userId="me", q=query, maxResults=25).execute().get("messages", [])
        return [self._metadata(reference) for reference in references]

    def find_sent_messages_by_message_id(self, outbound_message_id: str) -> list[dict[str, str]]:
        message_id = validate_outbound_message_id(outbound_message_id)
        query = f"in:sent rfc822msgid:{message_id}"
        return self._list_metadata(query)

    def find_sent_messages_for_record(self, record: dict[str, object]) -> list[dict[str, str]]:
        """Exact RFC-ID first; then a bounded, metadata-only Sent fallback."""
        exact = self.find_sent_messages_by_message_id(str(record["outbound_rfc_message_id"]))
        if exact:
            return exact
        recipient = str(record.get("reconciliation_recipient", ""))
        subject = str(record.get("reconciliation_subject", ""))
        thread_id = str(record.get("source_thread_id", ""))
        if thread_id:
            thread = self._service.users().threads().get(
                userId="me", id=thread_id, format="metadata", metadataHeaders=self._METADATA_HEADERS,
            ).execute()
            candidates = [
                self._metadata({"id": str(message["id"])})
                for message in thread.get("messages", []) if "SENT" in message.get("labelIds", [])
            ]
        elif recipient and subject:
            created = datetime.fromisoformat(str(record["created_at_utc"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            start = (created - timedelta(hours=1)).strftime("%Y/%m/%d")
            end = (created + timedelta(days=1)).strftime("%Y/%m/%d")
            candidates = self._list_metadata(
                f'in:sent from:{EXPECTED_ACCOUNT} to:{recipient} subject:"{subject}" after:{start} before:{end}'
            )
        else:
            return []
        return [
            item for item in candidates
            if recipient_fingerprint(item["from"]) == recipient_fingerprint(EXPECTED_ACCOUNT)
            and recipient_fingerprint(item["to"]) == record.get("recipient_hash")
            and fingerprint(item["subject"]) == record.get("subject_hash")
            and item.get("operation_id") == record.get("operation_id")
        ]


def verify_test_account(service: Resource) -> None:
    account = service.users().getProfile(userId="me").execute().get("emailAddress", "")
    if account.casefold() != EXPECTED_ACCOUNT.casefold():
        raise ValueError("Authenticated Gmail account does not match the approved TEST account.")


def create_live_readonly_adapter(
    credentials_loader: Callable[[], Credentials] = get_existing_readonly_credentials,
    service_builder: Callable[..., Resource] = build,
) -> GmailSentLiveAdapter:
    credentials = credentials_loader()
    service = service_builder("gmail", "v1", credentials=credentials, cache_discovery=False)
    verify_test_account(service)
    return GmailSentLiveAdapter(service)


def reconcile_existing_intent_read_only(
    operation_id: str,
    adapter: SentMetadataAdapter,
    automation_sender: str,
    *,
    directory: Path = OUTBOX_DIRECTORY,
) -> ReconciliationResult:
    """Read evidence for an intent without changing the outbox, ledgers, or Gmail state."""
    record = load_intent(operation_id, directory)
    if record is None:
        raise ValueError("Outbox intent was not found.")
    return reconcile_record(record, adapter, automation_sender)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Gmail Sent metadata lookup.")
    parser.add_argument("--live-read-only", action="store_true", help="Permit one live read-only Sent lookup.")
    parser.add_argument("--message-id", help="Existing deterministic outbound RFC Message-ID.")
    args = parser.parse_args()
    if not args.live_read_only:
        print("Live Gmail access is disabled. Use --live-read-only with an existing deterministic Message-ID.")
        return 0
    if not args.message_id:
        print("A deterministic outbound RFC Message-ID is required; no Gmail API call was made.")
        return 2
    try:
        message_id = validate_outbound_message_id(args.message_id)
        adapter = create_live_readonly_adapter()
        candidates = adapter.find_sent_messages_by_message_id(message_id)
    except (FileNotFoundError, ValueError) as error:
        print(f"Read-only lookup blocked: {error}")
        return 2
    print(f"Read-only Sent metadata candidates found: {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
