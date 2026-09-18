"""Read the linked Google Form response sheet using Sheets read-only OAuth."""

from __future__ import annotations

import re
from typing import Any
import unicodedata

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from config import CONFIG, PROJECT_ROOT


CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token_sheets.json"
SPREADSHEET_ID = CONFIG.form_response_spreadsheet_id
EXPECTED_ACCOUNT = CONFIG.gmail_account
# This module requests only read access to Google Sheets.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

FORM_HEADERS = (
    "Timestamp",
    "Order ID",
    "CX Number / Customer Number",
    "Issue / Problem Description",
    "Invoice",
    "State",
    "Pincode",
    "Complete Address",
    "Customer Image / Issue Image",
    "Additional Remarks",
)
# Output tabs can contain copied Form fields, but must never be used as response sources.
DEFAULT_EXCLUDED_FORM_RESPONSE_TABS = frozenset({"Case Results"})


def get_credentials() -> Credentials:
    """Load or obtain a Sheets-only OAuth token, kept separate from Gmail's token."""
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
                raise FileNotFoundError(f"OAuth client file not found: {CREDENTIALS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def normalize_header(value: str) -> str:
    """Normalize harmless display differences while preserving the header's meaning."""
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return re.sub(r"\s*/\s*", "/", value)


def quote_sheet_name(title: str) -> str:
    """Quote a tab name safely for A1 notation."""
    return "'" + title.replace("'", "''") + "'"


def read_values(service: Resource, range_name: str) -> list[list[str]]:
    """Read formatted cell values only; this is a Sheets read-only request."""
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            majorDimension="ROWS",
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    return response.get("values", [])


def find_form_response_sheet(
    service: Resource, excluded_tab_names: set[str] | frozenset[str] | None = None
) -> tuple[str, list[str]]:
    """Identify a Form response tab by headers while excluding configured output tabs."""
    metadata: dict[str, Any] = (
        service.spreadsheets()
        .get(
            spreadsheetId=SPREADSHEET_ID,
            fields="sheets(properties(title,sheetType))",
        )
        .execute()
    )
    required_headers = {
        normalize_header("Timestamp"),
        normalize_header("Order ID"),
        normalize_header("CX Number / Customer Number"),
        normalize_header("Issue / Problem Description"),
    }
    expected_headers = {normalize_header(header) for header in FORM_HEADERS}
    excluded = {
        normalize_header(title)
        for title in (DEFAULT_EXCLUDED_FORM_RESPONSE_TABS | frozenset(excluded_tab_names or set()))
    }
    matches: list[tuple[int, str, list[str]]] = []

    for sheet in metadata.get("sheets", []):
        properties = sheet.get("properties", {})
        if properties.get("sheetType") != "GRID":
            continue
        title = properties.get("title", "(untitled)")
        if normalize_header(title) in excluded:
            print(f"Sheet tab excluded from Form response detection: {title}")
            continue
        rows = read_values(service, f"{quote_sheet_name(title)}!1:1")
        headers = rows[0] if rows else []
        print(f"Sheet tab: {title}")
        print("Detected headers: " + (" | ".join(headers) if headers else "(none)"))
        normalized_headers = {normalize_header(header) for header in headers if header.strip()}
        if required_headers.issubset(normalized_headers):
            score = len(expected_headers.intersection(normalized_headers))
            matches.append((score, title, headers))

    if not matches:
        raise ValueError(
            "No sheet tab contains the required normalized Form response headers. "
            "Review the detected headers above."
        )
    highest_score = max(score for score, _, _ in matches)
    best_matches = [match for match in matches if match[0] == highest_score]
    if len(best_matches) > 1:
        names = ", ".join(title for _, title, _ in best_matches)
        raise ValueError(f"More than one tab matches the Form response headers: {names}")
    _, title, headers = best_matches[0]
    return title, headers


def cell_value(row: list[str], index: int) -> str:
    """Return one cell, including for short rows and blank cells."""
    return row[index].strip() if index < len(row) else ""


def nonempty_row(row: list[str]) -> bool:
    return any(cell.strip() for cell in row)


def print_latest_response(headers: list[str], rows: list[list[str]]) -> None:
    """Print the latest non-empty response row with absent values shown safely."""
    response_rows = [row for row in rows[1:] if nonempty_row(row)]
    print(f"Submitted response rows: {len(response_rows)}")
    if not response_rows:
        print("No submitted responses found.")
        return

    latest = response_rows[-1]
    labels = (
        ("Timestamp", "Timestamp"),
        ("Order ID", "Order ID"),
        ("CX Number", "CX Number / Customer Number"),
        ("Issue", "Issue / Problem Description"),
        ("Invoice", "Invoice"),
        ("State", "State"),
        ("Pincode", "Pincode"),
        ("Address", "Complete Address"),
        ("Image", "Customer Image / Issue Image"),
        ("Remarks", "Additional Remarks"),
    )
    index_by_header = {normalize_header(name): index for index, name in enumerate(headers)}
    print("Latest submitted response:")
    for label, header in labels:
        index = index_by_header.get(normalize_header(header))
        value = cell_value(latest, index) if index is not None else ""
        value = value or "(empty)"
        print(f"{label}: {value}")


def main() -> int:
    try:
        credentials = get_credentials()
        service: Resource = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        title, headers = find_form_response_sheet(service)
        print(f"Form response sheet: {title}")
        rows = read_values(service, quote_sheet_name(title))
        # Sheets read-only OAuth does not expose the signed-in account's email.
        # The browser consent screen must be used to select EXPECTED_ACCOUNT.
        print(f"OAuth account selected at consent must be: {EXPECTED_ACCOUNT}")
        print_latest_response(headers, rows)
        return 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
