"""Create and append immutable Case Results rows in the Form response spreadsheet."""

from __future__ import annotations

import msvcrt
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource

from sheets_reader import CREDENTIALS_FILE, SPREADSHEET_ID, quote_sheet_name
from config import CONFIG
from retry_utils import retry_call


WRITE_TOKEN_FILE = Path(__file__).resolve().parent.parent / "token_sheets_write.json"
WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CASE_RESULTS_TAB = CONFIG.case_results_tab
CASE_RESULTS_HEADERS = (
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
    "Case Count",
    "Case Statuses",
    "Result",
    "Response ID",
)
LEGACY_CASE_RESULTS_HEADERS = CASE_RESULTS_HEADERS[:-1]
FORM_FIELD_HEADERS = LEGACY_CASE_RESULTS_HEADERS[:10]
CASE_RESULTS_LOCK_FILE = Path(__file__).resolve().parent.parent / ".case_results_write.lock"


class CaseResultsLockUnavailableError(ValueError):
    """Raised when another local Case Results writer currently holds the lock."""


@contextmanager
def case_results_write_lock(path: Path = CASE_RESULTS_LOCK_FILE) -> Iterator[None]:
    """Prevent concurrent local read-check-append operations; not a distributed lock."""
    with path.open("a+b") as lock_file:
        lock_file.seek(0, 2)
        if lock_file.tell() == 0:
            lock_file.write(b"\\0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise CaseResultsLockUnavailableError(
                "Case Results is already being written by another local process."
            ) from error
        try:
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def get_write_credentials() -> Credentials:
    """Load a separate write-scoped token without changing the read-only token."""
    credentials: Credentials | None = None
    if WRITE_TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(WRITE_TOKEN_FILE, WRITE_SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                credentials = None
        if not credentials or not credentials.valid:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(f"OAuth client file not found: {CREDENTIALS_FILE}")
            credentials = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, WRITE_SCOPES
            ).run_local_server(port=0)
        WRITE_TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def ensure_case_results_tab(service: Resource) -> None:
    """Create the dedicated tab and its header once; never overwrite an existing header."""
    metadata_request = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID, fields="sheets(properties(sheetId,title))"
    )
    metadata = retry_call(metadata_request.execute, operation_name="case_results_metadata_read")
    existing = {
        sheet.get("properties", {}).get("title")
        for sheet in metadata.get("sheets", [])
    }
    if CASE_RESULTS_TAB not in existing:
        add_tab_request = service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": CASE_RESULTS_TAB}}}]},
        )
        retry_call(add_tab_request.execute, operation_name="case_results_add_tab")
        header_request = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{quote_sheet_name(CASE_RESULTS_TAB)}!A1:N1",
            valueInputOption="RAW",
            body={"values": [list(CASE_RESULTS_HEADERS)]},
        )
        retry_call(header_request.execute, operation_name="case_results_header_write")
        return

    header_request = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{quote_sheet_name(CASE_RESULTS_TAB)}!1:1",
        majorDimension="ROWS",
        valueRenderOption="FORMATTED_VALUE",
    )
    values = retry_call(header_request.execute, operation_name="case_results_header_read").get("values", [])
    header = values[0] if values else []
    if tuple(header) == CASE_RESULTS_HEADERS:
        return
    if tuple(header) == LEGACY_CASE_RESULTS_HEADERS:
        upgrade_request = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{quote_sheet_name(CASE_RESULTS_TAB)}!N1",
            valueInputOption="RAW",
            body={"values": [["Response ID"]]},
        )
        retry_call(upgrade_request.execute, operation_name="case_results_response_id_header_upgrade")
        return
    raise ValueError("Existing Case Results header does not match the required schema.")


def result_values(
    form_fields: dict[str, str], statuses: list[str], response_id: str
) -> list[str | int]:
    """Build one Case Results row without changing source Form values."""
    found = bool(statuses)
    return [
        *[form_fields.get(header, "") for header in FORM_FIELD_HEADERS],
        len(statuses),
        " | ".join(statuses) if found else "ORDER ID NOT FOUND IN CASES",
        "MATCH FOUND" if found else "NOT FOUND",
        response_id,
    ]


def case_result_exists(service: Resource, response_id: str) -> bool:
    """Check only Response ID values; blank legacy IDs never suppress new submissions."""
    rows_request = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{quote_sheet_name(CASE_RESULTS_TAB)}!N2:N",
        majorDimension="ROWS",
        valueRenderOption="FORMATTED_VALUE",
    )
    rows = retry_call(rows_request.execute, operation_name="case_results_duplicate_read").get("values", [])
    for row in rows:
        if row and row[0] == response_id:
            return True
    return False


def _append_case_result_once(
    service: Resource, form_fields: dict[str, str], statuses: list[str], response_id: str
) -> bool:
    """Append exactly one result row unless its original Form response is already present."""
    ensure_case_results_tab(service)
    if case_result_exists(service, response_id):
        return False
    append_request = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{quote_sheet_name(CASE_RESULTS_TAB)}!A:N",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [result_values(form_fields, statuses, response_id)]},
    )
    append_request.execute()
    return True


def append_case_result(
    service: Resource,
    form_fields: dict[str, str],
    statuses: list[str],
    response_id: str,
    lock_path: Path = CASE_RESULTS_LOCK_FILE,
) -> bool:
    """Append once per Response ID, rechecking after transient append uncertainty."""
    with case_results_write_lock(lock_path):
        return retry_call(
            lambda: _append_case_result_once(service, form_fields, statuses, response_id),
            operation_name="case_results_append",
        )
