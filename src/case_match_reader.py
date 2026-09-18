"""Read the latest Form Order ID and list every matching status from Cases."""

from __future__ import annotations

from cases_sheet_source import read_cases_rows
from case_matching import find_all_case_statuses, normalize_order_id
from sheets_reader import (
    EXPECTED_ACCOUNT,
    cell_value,
    find_form_response_sheet,
    get_credentials,
    nonempty_row,
    normalize_header,
    quote_sheet_name,
    read_values,
)
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError


def latest_form_order_id(headers: list[str], rows: list[list[str]]) -> str:
    """Return the latest non-empty Form response's Order ID, safely."""
    order_id_index = next(
        (
            index
            for index, header in enumerate(headers)
            if normalize_header(header) == normalize_header("Order ID")
        ),
        None,
    )
    if order_id_index is None:
        raise ValueError("The detected Form response tab has no Order ID header.")

    for row in reversed(rows[1:]):
        if nonempty_row(row):
            return normalize_order_id(cell_value(row, order_id_index))
    return ""


def print_match_result(order_id: str, statuses: list[str]) -> None:
    """Print every matching status, including a clear no-match result."""
    display_order_id = order_id or "(blank)"
    print(f"Order ID: {display_order_id}")
    print()
    print(f"Matching Cases: {len(statuses)}")
    print()
    if not order_id:
        print("(blank) - ORDER ID NOT FOUND IN CASES")
        return
    if not statuses:
        print(f"{order_id} - ORDER ID NOT FOUND IN CASES")
        return
    for status in statuses:
        print(f"{order_id} - {status or '(blank status)'}")


def main() -> int:
    try:
        credentials = get_credentials()
        service: Resource = build("sheets", "v4", credentials=credentials, cache_discovery=False)

        form_title, form_headers = find_form_response_sheet(service)
        form_rows = read_values(service, quote_sheet_name(form_title))
        order_id = latest_form_order_id(form_headers, form_rows)

        # This reads the complete current Cases range A:G; it is never cached or written.
        case_rows = read_cases_rows(service)
        statuses = find_all_case_statuses(order_id, case_rows)

        print(f"Form response sheet: {form_title}")
        print(f"OAuth account selected at consent must be: {EXPECTED_ACCOUNT}")
        print_match_result(order_id, statuses)
        return 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
