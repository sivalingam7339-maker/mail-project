"""Read the latest Form submission and match its Order ID against current Cases."""

from __future__ import annotations

from typing import Any

from case_matching import find_all_case_statuses, normalize_order_id
from cases_sheet_source import read_cases_rows
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from sheets_reader import (
    SCOPES,
    TOKEN_FILE,
    cell_value,
    find_form_response_sheet,
    nonempty_row,
    normalize_header,
    quote_sheet_name,
    read_values,
)


def load_existing_sheets_credentials() -> Credentials:
    """Load the existing Sheets token without writing, replacing, or deleting it."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Existing Sheets token not found: {TOKEN_FILE}")
    credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not credentials.valid:
        if not credentials.expired or not credentials.refresh_token:
            raise ValueError("Existing Sheets token is invalid; re-authorize it with the Sheets reader.")
        try:
            credentials.refresh(Request())
        except RefreshError as error:
            raise ValueError("Existing Sheets token could not be refreshed.") from error
    return credentials


def header_index(headers: list[str], header_name: str) -> int:
    """Find a column by the same safe header normalization used by the Sheets reader."""
    target = normalize_header(header_name)
    for index, header in enumerate(headers):
        if normalize_header(header) == target:
            return index
    raise ValueError(f"The detected Form response tab has no {header_name!r} header.")


def column_letter(index: int) -> str:
    """Convert a zero-based column index to an A1 column label."""
    result = ""
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def timestamp_values(service: Resource, tab_name: str, timestamp_index: int) -> list[list[Any]]:
    """Read timestamp serial values so latest-row selection is independent of row order."""
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId="1HcMJO_hLRYmAeanmwpEXtJQHSL0Ik5y40GyIW8Psb6g",
            range=f"{quote_sheet_name(tab_name)}!{column_letter(timestamp_index)}:{column_letter(timestamp_index)}",
            majorDimension="ROWS",
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="SERIAL_NUMBER",
        )
        .execute()
    )
    return response.get("values", [])


def latest_form_submission(
    headers: list[str], form_rows: list[list[str]], raw_timestamps: list[list[Any]]
) -> tuple[str, str]:
    """Return the displayed timestamp and Order ID from the newest non-empty response."""
    timestamp_index = header_index(headers, "Timestamp")
    order_id_index = header_index(headers, "Order ID")
    candidates: list[tuple[float, int, list[str]]] = []

    for row_number, row in enumerate(form_rows[1:], start=2):
        if not nonempty_row(row):
            continue
        raw_value = raw_timestamps[row_number - 1][0] if row_number - 1 < len(raw_timestamps) and raw_timestamps[row_number - 1] else None
        try:
            timestamp_key = float(raw_value)
        except (TypeError, ValueError):
            continue
        candidates.append((timestamp_key, row_number, row))

    if not candidates:
        raise ValueError("No non-empty Form response rows with a valid Timestamp were found.")
    _, _, latest_row = max(candidates, key=lambda candidate: (candidate[0], candidate[1]))
    return (
        cell_value(latest_row, timestamp_index) or "(empty)",
        normalize_order_id(cell_value(latest_row, order_id_index)),
    )


def print_case_result(timestamp: str, order_id: str, statuses: list[str]) -> None:
    """Print all matches, preserving duplicate Cases rows in the output."""
    display_order_id = order_id or "(blank)"
    print("Latest Form Submission")
    print("----------------------")
    print(f"Timestamp: {timestamp}")
    print(f"Order ID: {display_order_id}")
    print()
    print("Case Matching Result")
    print("--------------------")
    print(f"Matching Cases: {len(statuses)}")
    print()
    if not order_id or not statuses:
        print(f"{display_order_id} - ORDER ID NOT FOUND IN CASES")
        return
    for status in statuses:
        print(f"{order_id} - {status or '(blank status)'}")


def main() -> int:
    try:
        credentials = load_existing_sheets_credentials()
        service: Resource = build("sheets", "v4", credentials=credentials, cache_discovery=False)

        form_tab, headers = find_form_response_sheet(service)
        form_rows = read_values(service, quote_sheet_name(form_tab))
        timestamp_index = header_index(headers, "Timestamp")
        timestamp, order_id = latest_form_submission(
            headers, form_rows, timestamp_values(service, form_tab, timestamp_index)
        )

        # Always retrieve all currently available Cases rows; nothing is cached or written.
        statuses = find_all_case_statuses(order_id, read_cases_rows(service))
        print_case_result(timestamp, order_id, statuses)
        return 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
