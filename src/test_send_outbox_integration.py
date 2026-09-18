"""Fake-only integration tests for Gmail outbox adapters; no API calls are made."""

from __future__ import annotations

import base64
import tempfile
from email import message_from_bytes
from pathlib import Path

import form_reply_sender as customer
import internal_case_notifier as internal
import send_outbox as outbox


CUSTOMER_MESSAGE = {
    "message_id": "incoming-1",
    "thread_id": "thread-1",
    "sender": "customer@example.test",
    "subject": "Need help with product",
    "rfc_message_id": "<incoming@example.test>",
    "references": "<root@example.test>",
}
FORM_FIELDS = {
    "Order ID": "order-1",
    "CX Number / Customer Number": "cx-1",
    "Issue / Problem Description": "Issue",
    "Timestamp": "2026-01-01 10:00",
    "State": "State",
    "Pincode": "000000",
    "Complete Address": "address",
    "Additional Remarks": "",
    "Invoice": "",
    "Customer Image / Issue Image": "",
}


def headers(payload: dict[str, str]) -> object:
    return message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        sent_payloads: list[dict[str, str]] = []
        ledger_writes: list[str] = []

        def customer_send(payload: dict[str, str]) -> dict[str, str]:
            record = outbox.load_intent(outbox.customer_reply_operation_id("incoming-1"), directory)
            assert record and record["status"] == outbox.SENDING
            sent_payloads.append(payload)
            return {"id": "customer-sent", "threadId": "thread-1"}

        outcome = customer.send_customer_reply_with_outbox(
            None, CUSTOMER_MESSAGE, set(), send_callable=customer_send,
            ledger_callback=lambda message_id, _: ledger_writes.append(message_id), outbox_directory=directory,
        )
        assert outcome.status == outbox.LEDGER_RECORDED and len(sent_payloads) == 1 and ledger_writes == ["incoming-1"]
        email = headers(sent_payloads[0])
        assert email["To"] == CUSTOMER_MESSAGE["sender"] and email["In-Reply-To"] == CUSTOMER_MESSAGE["rfc_message_id"]
        assert email["Message-ID"] == outbox.outbound_rfc_message_id(outbox.customer_reply_operation_id("incoming-1"))
        assert email["X-Customer-Case-Operation-ID"] == outbox.customer_reply_operation_id("incoming-1")
        repeat = customer.send_customer_reply_with_outbox(
            None, CUSTOMER_MESSAGE, set(), send_callable=lambda _: (_ for _ in ()).throw(AssertionError("duplicate send")),
            ledger_callback=lambda message_id, _: ledger_writes.append(message_id), outbox_directory=directory,
        )
        assert repeat.status == outbox.LEDGER_RECORDED and len(sent_payloads) == 1 and ledger_writes == ["incoming-1"]

        uncertain_message = {**CUSTOMER_MESSAGE, "message_id": "incoming-uncertain"}
        uncertain_writes: list[str] = []
        uncertain = customer.send_customer_reply_with_outbox(
            None, uncertain_message, set(), send_callable=lambda _: (_ for _ in ()).throw(TimeoutError("fake")),
            ledger_callback=lambda message_id, _: uncertain_writes.append(message_id), outbox_directory=directory,
        )
        assert uncertain.status == outbox.RECONCILIATION_REQUIRED and not uncertain_writes
        retry = customer.send_customer_reply_with_outbox(
            None, uncertain_message, set(), send_callable=lambda _: (_ for _ in ()).throw(AssertionError("must not resend")),
            ledger_callback=lambda message_id, _: uncertain_writes.append(message_id), outbox_directory=directory,
        )
        assert retry.status == outbox.RECONCILIATION_REQUIRED and not uncertain_writes

        internal_payloads: list[dict[str, str]] = []

        def internal_send(payload: dict[str, str]) -> dict[str, str]:
            record = outbox.load_intent(outbox.internal_notification_operation_id("response-1"), directory)
            assert record and record["status"] == outbox.SENDING
            internal_payloads.append(payload)
            return {"id": "internal-sent", "threadId": ""}

        notification = internal.send_notification_with_outbox(
            None, FORM_FIELDS, ["Open"], "response-1", send_callable=internal_send, outbox_directory=directory
        )
        assert notification.status == outbox.SENT_CONFIRMED and len(internal_payloads) == 1
        email = headers(internal_payloads[0])
        operation_id = outbox.internal_notification_operation_id("response-1")
        assert email["Message-ID"] == outbox.outbound_rfc_message_id(operation_id)
        assert email["X-Customer-Case-Operation-ID"] == operation_id
        restart = internal.send_notification_with_outbox(
            None, FORM_FIELDS, ["Open"], "response-1",
            send_callable=lambda _: (_ for _ in ()).throw(AssertionError("must not resend")), outbox_directory=directory,
        )
        assert restart.status == outbox.SENT_CONFIRMED and len(internal_payloads) == 1

        unresolved = internal.send_notification_with_outbox(
            None, FORM_FIELDS, ["Open"], "response-uncertain",
            send_callable=lambda _: (_ for _ in ()).throw(ConnectionError("fake")), outbox_directory=directory,
        )
        assert unresolved.status == outbox.RECONCILIATION_REQUIRED
        assert unresolved.status != outbox.SENT_CONFIRMED
    print("Send outbox integration tests passed: customer/internal ordering, headers, restart safety, and unresolved blocking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
