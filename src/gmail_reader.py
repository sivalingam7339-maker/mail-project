"""Read and print the newest Gmail messages with read-only OAuth access."""

from __future__ import annotations

import base64
import sys
from email import message_from_bytes
from email.message import Message
from html import unescape
from html.parser import HTMLParser
from typing import Any, Iterable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from config import CONFIG, PROJECT_ROOT


CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"
EXPECTED_ACCOUNT = CONFIG.gmail_account
# gmail.readonly permits reading only; it cannot send, modify, or delete messages.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class _HTMLToText(HTMLParser):
    """Small, dependency-free HTML-to-text fallback for HTML-only messages."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def get_credentials() -> Credentials:
    """Load, refresh, or obtain OAuth credentials without embedding secrets."""
    credentials: Credentials | None = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                TOKEN_FILE.unlink(missing_ok=True)
                credentials = None

        if not credentials or not credentials.valid:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"OAuth client file not found: {CREDENTIALS_FILE}\n"
                    "Download a Desktop app OAuth client JSON from Google Cloud "
                    "and save it as credentials.json in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def header(headers: Iterable[dict[str, str]], name: str) -> str:
    """Return a message header safely, including when it is absent."""
    name = name.casefold()
    return next(
        (item.get("value", "") for item in headers if item.get("name", "").casefold() == name),
        "(missing)",
    )


def decode_base64url(data: str) -> bytes:
    """Decode Gmail's URL-safe base64 data, tolerating omitted padding."""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    parser.close()
    return unescape(parser.text())


def decode_part(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    raw = decode_base64url(data)
    content_type = part.get("mimeType", "text/plain")
    # The email library safely respects declared charsets and replaces bad bytes.
    parsed: Message = message_from_bytes(
        b"Content-Type: " + content_type.encode("ascii", "replace") + b"\r\n\r\n" + raw
    )
    text = parsed.get_payload(decode=True) or b""
    decoded = text.decode(parsed.get_content_charset() or "utf-8", errors="replace")
    return html_to_text(decoded) if content_type.casefold().startswith("text/html") else decoded


def body_text(payload: dict[str, Any]) -> str:
    """Prefer plain text; safely derive text if a message is HTML-only."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "").casefold()
        if mime_type == "text/plain":
            plain_parts.append(decode_part(part))
        elif mime_type == "text/html":
            html_parts.append(decode_part(part))
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    result = "\n".join(part for part in plain_parts if part).strip()
    if result:
        return result
    result = "\n".join(part for part in html_parts if part).strip()
    return result or "(no readable plain-text body)"


def print_message(message: dict[str, Any], index: int) -> None:
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    print(f"\n{'=' * 72}\nMessage {index}")
    print(f"From: {header(headers, 'From')}")
    print(f"To: {header(headers, 'To')}")
    print(f"Subject: {header(headers, 'Subject')}")
    print(f"Date: {header(headers, 'Date')}")
    print(f"Email ID: {message.get('id', '(missing)')}")
    print("Body:")
    print(body_text(payload))


def main() -> int:
    try:
        credentials = get_credentials()
        service: Resource = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        authenticated_email = profile.get("emailAddress", "(unknown)")
        print(f"Authenticated Gmail account: {authenticated_email}")

        if authenticated_email.casefold() != EXPECTED_ACCOUNT.casefold():
            print(
                f"WARNING: Expected test account {EXPECTED_ACCOUNT}, but authenticated "
                f"{authenticated_email}. No messages will be displayed.",
                file=sys.stderr,
            )
            return 2

        response = service.users().messages().list(userId="me", maxResults=10).execute()
        message_refs = response.get("messages", [])
        if not message_refs:
            print("No messages found.")
            return 0

        print(f"Reading {len(message_refs)} newest message(s) (read-only).")
        for index, ref in enumerate(message_refs, start=1):
            message = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            print_message(message, index)
        return 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
