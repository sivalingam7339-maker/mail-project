"""Fake-only strict reconciliation/header tests; no live Gmail or Google API use."""

from __future__ import annotations

import base64
import tempfile
from email import message_from_bytes
from pathlib import Path

import form_reply_sender as customer
import internal_case_notifier as internal
import gmail_sent_reconciliation as reconciliation
import send_outbox as outbox


MESSAGE = {
    "message_id": "incoming-24b", "thread_id": "thread-24b", "sender": "customer@test",
    "subject": "Help", "rfc_message_id": "<incoming-24b@test>", "references": "",
}
FIELDS = {
    "Order ID": "order-24b", "CX Number / Customer Number": "cx", "Issue / Problem Description": "issue",
    "Timestamp": "2026-01-01", "State": "state", "Pincode": "000000", "Complete Address": "address",
    "Additional Remarks": "", "Invoice": "", "Customer Image / Issue Image": "",
}


def mime_headers(payload: dict[str, str]):
    return message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))


def customer_candidate(record: dict[str, object]) -> dict[str, str]:
    return {
        "gmail_message_id": "gmail-customer", "thread_id": MESSAGE["thread_id"], "from": "automation@test",
        "to": MESSAGE["sender"], "subject": customer.reply_subject(MESSAGE["subject"]),
        "message_id": str(record["outbound_rfc_message_id"]), "operation_id": str(record["operation_id"]),
        "message_fingerprint": str(record["message_fingerprint"]), "outbound_message_id": str(record["outbound_message_id_marker"]), "in_reply_to": MESSAGE["rfc_message_id"],
    }


def internal_candidate(record: dict[str, object]) -> dict[str, str]:
    return {
        "gmail_message_id": "gmail-internal", "thread_id": "", "from": "automation@test",
        "to": internal.NOTIFICATION_RECIPIENT, "subject": "New Customer Case - order-24b",
        "message_id": str(record["outbound_rfc_message_id"]), "operation_id": str(record["operation_id"]),
        "message_fingerprint": str(record["message_fingerprint"]), "outbound_message_id": str(record["outbound_message_id_marker"]),
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        customer_intent = outbox.create_customer_reply_intent(
            source_message_id=MESSAGE["message_id"], source_rfc_message_id=MESSAGE["rfc_message_id"],
            source_thread_id=MESSAGE["thread_id"], recipient=MESSAGE["sender"],
            subject=customer.reply_subject(MESSAGE["subject"]), intended_content=customer.REPLY_CONTENT, directory=directory,
        )
        reply = customer.build_reply(
            MESSAGE, str(customer_intent["outbound_rfc_message_id"]), str(customer_intent["operation_id"]),
            str(customer_intent["message_fingerprint"]), str(customer_intent["outbound_message_id_marker"]),
        )
        headers = mime_headers(reply)
        assert headers["Message-ID"] == customer_intent["outbound_rfc_message_id"]
        assert headers["X-Customer-Case-Outbound-Message-ID"] == customer_intent["outbound_message_id_marker"]
        assert headers["X-Customer-Case-Operation-ID"] == customer_intent["operation_id"]
        assert headers["X-Customer-Case-Message-Fingerprint"] == customer_intent["message_fingerprint"]
        assert outbox.message_fingerprint(MESSAGE["sender"], "Re: Help", customer.REPLY_CONTENT, str(customer_intent["operation_id"])) == customer_intent["message_fingerprint"]
        assert outbox.message_fingerprint("other@test", "Re: Help", customer.REPLY_CONTENT, str(customer_intent["operation_id"])) != customer_intent["message_fingerprint"]
        assert outbox.message_fingerprint(MESSAGE["sender"], "Other", customer.REPLY_CONTENT, str(customer_intent["operation_id"])) != customer_intent["message_fingerprint"]
        assert outbox.message_fingerprint(MESSAGE["sender"], "Re: Help", "other", str(customer_intent["operation_id"])) != customer_intent["message_fingerprint"]

        internal_intent = outbox.create_internal_notification_intent(
            response_id="response-24b", recipient=internal.NOTIFICATION_RECIPIENT,
            subject="New Customer Case - order-24b", intended_content=internal.notification_body(FIELDS, ["Open"]), directory=directory,
        )
        notification = internal.build_notification(
            FIELDS, ["Open"], str(internal_intent["outbound_rfc_message_id"]), str(internal_intent["operation_id"]),
            str(internal_intent["message_fingerprint"]), str(internal_intent["outbound_message_id_marker"]),
        )
        headers = mime_headers(notification)
        assert headers["Message-ID"] == internal_intent["outbound_rfc_message_id"]
        assert headers["X-Customer-Case-Outbound-Message-ID"] == internal_intent["outbound_message_id_marker"]
        assert headers["X-Customer-Case-Operation-ID"] == internal_intent["operation_id"]
        assert headers["X-Customer-Case-Message-Fingerprint"] == internal_intent["message_fingerprint"]

        customer_operation = str(customer_intent["operation_id"])
        outbox.transition_intent(customer_operation, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(customer_operation, "fake_timeout", directory=directory)
        customer_ledger: list[str] = []
        outcome = customer.reconcile_customer_reply_with_outbox(
            MESSAGE, set(), reconciliation.FakeSentMetadataAdapter([customer_candidate(customer_intent)]), "automation@test",
            ledger_callback=lambda message_id, _: customer_ledger.append(message_id), outbox_directory=directory,
        )
        assert outcome.status == outbox.LEDGER_RECORDED and customer_ledger == [MESSAGE["message_id"]]
        assert customer.reconcile_customer_reply_with_outbox(
            MESSAGE, set(), reconciliation.FakeSentMetadataAdapter([]), "automation@test",
            ledger_callback=lambda *_: (_ for _ in ()).throw(AssertionError("duplicate ledger")), outbox_directory=directory,
        ).status == outbox.LEDGER_RECORDED

        internal_operation = str(internal_intent["operation_id"])
        outbox.transition_intent(internal_operation, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(internal_operation, "fake_timeout", directory=directory)
        internal_ledger: list[str] = []
        outcome, notified = internal.reconcile_notification_with_outbox(
            "response-24b", set(), reconciliation.FakeSentMetadataAdapter([internal_candidate(internal_intent)]), "automation@test",
            ledger_callback=lambda response_id, ids: (internal_ledger.append(response_id) or ids | {response_id}), outbox_directory=directory,
        )
        assert outcome.status == outbox.LEDGER_RECORDED and notified == {"response-24b"} and internal_ledger == ["response-24b"]

        unresolved = outbox.create_customer_reply_intent(
            source_message_id="incoming-unresolved-24b", source_rfc_message_id=MESSAGE["rfc_message_id"],
            source_thread_id=MESSAGE["thread_id"], recipient=MESSAGE["sender"], subject="Re: Help",
            intended_content=customer.REPLY_CONTENT, directory=directory,
        )
        unresolved_id = str(unresolved["operation_id"])
        outbox.transition_intent(unresolved_id, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(unresolved_id, "fake_timeout", directory=directory)
        for candidates in ([], [{**customer_candidate(unresolved), "to": "wrong"}], [customer_candidate(unresolved), customer_candidate(unresolved)]):
            outcome = customer.reconcile_customer_reply_with_outbox(
                {**MESSAGE, "message_id": "incoming-unresolved-24b"}, set(),
                reconciliation.FakeSentMetadataAdapter(candidates), "automation@test",
                ledger_callback=lambda *_: (_ for _ in ()).throw(AssertionError("unresolved ledger")), outbox_directory=directory,
            )
            assert outcome.status == outbox.RECONCILIATION_REQUIRED
            assert outbox.load_intent(unresolved_id, directory)["status"] == outbox.RECONCILIATION_REQUIRED  # type: ignore[index]
    print("Step 24B tests passed: fingerprint headers, strict confirmation, ledger ordering, and unresolved blocking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
