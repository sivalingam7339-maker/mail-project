"""Read the current testing Cases data from Google Sheets without modifying it."""

from __future__ import annotations

from googleapiclient.discovery import Resource

from config import CONFIG
from retry_utils import retry_call


CASES_SPREADSHEET_ID = CONFIG.cases_spreadsheet_id
CASES_SHEET_TAB = CONFIG.cases_sheet_tab


def quote_sheet_name(title: str) -> str:
    """Quote a sheet tab safely for A1 notation."""
    return "'" + title.replace("'", "''") + "'"


def read_cases_rows(service: Resource) -> list[list[str]]:
    """Return all currently available Cases rows, columns A through G, read-only."""
    request = service.spreadsheets().values().get(
        spreadsheetId=CASES_SPREADSHEET_ID,
        range=f"{quote_sheet_name(CASES_SHEET_TAB)}!A:G",
        majorDimension="ROWS",
        valueRenderOption="FORMATTED_VALUE",
    )
    response = retry_call(request.execute, operation_name="cases_sheet_read")
    return response.get("values", [])
