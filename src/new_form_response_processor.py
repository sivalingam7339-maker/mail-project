"""Process each unrecorded Google Form response using read-only Cases matching."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from case_matching import find_all_case_statuses, normalize_order_id
from cases_sheet_source import read_cases_rows
from case_results_writer import (
    FORM_FIELD_HEADERS,
    append_case_result,
    get_write_credentials,
)
from form_case_match import (
    header_index,
    timestamp_values,
)
from internal_case_notifier import (
    NOTIFICATION_RECIPIENT,
    get_notification_service,
    load_notified_ids,
    record_notified_id,
    send_notification_with_outbox,
)
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from sheets_reader import (
    cell_value,
    find_form_response_sheet,
    nonempty_row,
    quote_sheet_name,
    read_values,
)
from send_outbox import (
    LEDGER_RECORDED,
    SENT_CONFIRMED,
    internal_notification_operation_id,
    load_intent,
    mark_ledger_recorded,
)


LEDGER_FILE = Path(__file__).resolve().parent.parent / ".form_processed_response_ids.json"


def load_processed_ids() -> set[str]:
    """Load the local response ledger without contacting or changing Google Sheets."""
    if not LEDGER_FILE.exists():
        return set()
    data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("Form response processing ledger has an invalid format.")
    return set(data)


def record_processed_id(response_id: str, processed_ids: set[str]) -> set[str]:
    """Atomically add one ID only after its matching operation has completed."""
    updated_ids = processed_ids | {response_id}
    temporary_file = LEDGER_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(sorted(updated_ids), indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(LEDGER_FILE)
    return updated_ids


def response_id(row_number: int, timestamp: str, order_id: str) -> str:
    """Create a deterministic ID from a response's row, timestamp, and Order ID."""
    material = f"{row_number}\x1f{timestamp}\x1f{order_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def collect_responses(
    headers: list[str], rows: list[list[str]], raw_timestamps: list[list[Any]]
) -> list[dict[str, str | float | int]]:
    """Return every non-empty response, ordered chronologically by Sheets timestamp."""
    timestamp_index = header_index(headers, "Timestamp")
    order_id_index = header_index(headers, "Order ID")
    cx_index = header_index(headers, "CX Number / Customer Number")
    issue_index = header_index(headers, "Issue / Problem Description")
    field_indexes = {header: header_index(headers, header) for header in FORM_FIELD_HEADERS}
    responses: list[dict[str, str | float | int]] = []

    for row_number, row in enumerate(rows[1:], start=2):
        if not nonempty_row(row):
            continue
        raw_timestamp = (
            raw_timestamps[row_number - 1][0]
            if row_number - 1 < len(raw_timestamps) and raw_timestamps[row_number - 1]
            else None
        )
        try:
            timestamp_key = float(raw_timestamp)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Form response on sheet row {row_number} has an invalid Timestamp.") from error
        timestamp = cell_value(row, timestamp_index)
        order_id = normalize_order_id(cell_value(row, order_id_index))
        responses.append(
            {
                "id": response_id(row_number, timestamp, order_id),
                "timestamp_key": timestamp_key,
                "row_number": row_number,
                "timestamp": timestamp,
                "order_id": order_id,
                "cx_number": cell_value(row, cx_index),
                "issue": cell_value(row, issue_index),
                "form_fields": {
                    header: cell_value(row, index) for header, index in field_indexes.items()
                },
            }
        )
    return sorted(responses, key=lambda response: (float(response["timestamp_key"]), int(response["row_number"])))


def print_response(response: dict[str, str | float | int], statuses: list[str]) -> None:
    """Print one response and every current Cases status for its Order ID."""
    order_id = str(response["order_id"]) or "(blank)"
    print("Processing response...")
    print()
    print("New Form Response")
    print("-----------------")
    print(f"Sheet Row: {response['row_number']}")
    print(f"Timestamp: {response['timestamp'] or '(empty)'}")
    print(f"Order ID: {order_id}")
    print(f"CX Number: {response['cx_number'] or '(empty)'}")
    print(f"Issue: {response['issue'] or '(empty)'}")
    print()
    print("Case Matching Result")
    print("--------------------")
    print(f"Matching Cases: {len(statuses)}")
    print()
    if not statuses:
        print(f"{order_id} - ORDER ID NOT FOUND IN CASES")
    else:
        for status in statuses:
            print(f"{order_id} - {status or '(blank status)'}")


def main() -> int:
    try:
        print("Checking for new Form responses...")
        service: Resource = build("sheets", "v4", credentials=get_write_credentials(), cache_discovery=False)
        form_tab, headers = find_form_response_sheet(service)
        form_rows = read_values(service, quote_sheet_name(form_tab))
        timestamp_index = header_index(headers, "Timestamp")
        responses = collect_responses(
            headers, form_rows, timestamp_values(service, form_tab, timestamp_index)
        )
        processed_ids = load_processed_ids()
        new_responses = [response for response in responses if str(response["id"]) not in processed_ids]
        already_processed = len(responses) - len(new_responses)
        print(f"New responses found: {len(new_responses)}")
        print(f"Already processed: {already_processed}")
        if not new_responses:
            print("No new responses found.")
            print()
            print("Processing Summary")
            print("------------------")
            print("Processed: 0")
            print(f"Skipped already processed: {already_processed}")
            print("Failed: 0")
            print("Notifications sent: 0")
            print("Notifications failed: 0")
            return 0

        # Read every currently available Cases row once for this run; no local cache is kept.
        case_rows = read_cases_rows(service)
        notified_ids = load_notified_ids()
        notification_service: Resource | None = None
        processed_count = 0
        failed_count = 0
        notifications_sent = 0
        notifications_failed = 0
        for response in new_responses:
            try:
                statuses = find_all_case_statuses(str(response["order_id"]), case_rows)
                print_response(response, statuses)
                print("Writing Case Result...")
                appended = append_case_result(
                    service, response["form_fields"], statuses, str(response["id"])
                )
                if appended:
                    print("Case result saved successfully.")
                else:
                    print("Case result already exists; no duplicate row was appended.")
                if str(response["id"]) in notified_ids:
                    operation_id = internal_notification_operation_id(str(response["id"]))
                    intent = load_intent(operation_id)
                    if intent and intent["status"] == SENT_CONFIRMED:
                        mark_ledger_recorded(operation_id)
                    elif intent and intent["status"] != LEDGER_RECORDED:
                        raise ValueError(
                            "Internal notification ledger and outbox state disagree; automatic resend is blocked."
                        )
                    print("Internal notification was already sent; no duplicate notification was sent.")
                else:
                    print("Preparing internal notification...")
                    print(f"To: {NOTIFICATION_RECIPIENT}")
                    print(f"Subject: New Customer Case - {response['order_id'] or '(blank)'}")
                    try:
                        notification_service = notification_service or get_notification_service()
                        outcome = send_notification_with_outbox(
                            notification_service,
                            response["form_fields"],
                            statuses,
                            str(response["id"]),
                        )
                    except (HttpError, OSError, ValueError) as error:
                        raise ValueError(f"Internal notification failed: {error}") from error
                    if outcome.status == SENT_CONFIRMED:
                        notified_ids = record_notified_id(str(response["id"]), notified_ids)
                        mark_ledger_recorded(
                            f"internal_notification:v1:{response['id']}"
                        )
                        notifications_sent += 1
                        print("Internal notification sent successfully.")
                    elif outcome.status == LEDGER_RECORDED:
                        raise ValueError(
                            "Internal notification outbox indicates a recorded ledger, but the local notification ledger is missing the Response ID."
                        )
                    else:
                        raise ValueError(
                            f"Internal notification outbox requires safe recovery: {outcome.status}"
                        )
                processed_ids = record_processed_id(str(response["id"]), processed_ids)
                print("Response processed successfully.")
                processed_count += 1
            except (HttpError, OSError, ValueError) as error:
                failed_count += 1
                if "notification" in str(error).casefold():
                    notifications_failed += 1
                    print(f"Internal notification failed: {error}")
                else:
                    print(f"Failed to process sheet row {response['row_number']}: {error}")
                print("Response was NOT marked as processed and will be retried.")
        print()
        print("Processing Summary")
        print("------------------")
        print(f"Processed: {processed_count}")
        print(f"Skipped already processed: {already_processed}")
        print(f"Failed: {failed_count}")
        print(f"Notifications sent: {notifications_sent}")
        print(f"Notifications failed: {notifications_failed}")
        return 1 if failed_count else 0
    except (FileNotFoundError, HttpError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
