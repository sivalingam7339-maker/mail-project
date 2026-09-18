"""Local fake-metadata tests for strict Sent reconciliation; no Gmail client is used."""

from __future__ import annotations

import tempfile
from pathlib import Path

import gmail_sent_reconciliation as reconciliation
import send_outbox as outbox


def customer_record(directory: Path, source_message_id: str = "incoming-1") -> dict[str, object]:
    return outbox.create_customer_reply_intent(
        source_message_id=source_message_id, source_rfc_message_id="<incoming@test>", source_thread_id="thread-1",
        recipient="customer@test", subject="Re: Support request", intended_content="support form", directory=directory,
    )


def internal_record(directory: Path) -> dict[str, object]:
    return outbox.create_internal_notification_intent(
        response_id="response-1", recipient="internal@test", subject="New Customer Case - order-1",
        intended_content="case summary", directory=directory,
    )


def customer_candidate(record: dict[str, object]) -> dict[str, str]:
    return {
        "gmail_message_id": "gmail-sent-1", "thread_id": "thread-1", "from": "automation@test",
        "to": "customer@test", "subject": "Re: Support request", "message_id": str(record["outbound_rfc_message_id"]),
        "operation_id": str(record["operation_id"]), "message_fingerprint": str(record["message_fingerprint"]),
        "outbound_message_id": str(record["outbound_message_id_marker"]),
        "in_reply_to": "<incoming@test>",
    }


def internal_candidate(record: dict[str, object]) -> dict[str, str]:
    return {
        "gmail_message_id": "gmail-internal-1", "thread_id": "", "from": "automation@test",
        "to": "internal@test", "subject": "New Customer Case - order-1", "message_id": str(record["outbound_rfc_message_id"]),
        "operation_id": str(record["operation_id"]), "message_fingerprint": str(record["message_fingerprint"]),
        "outbound_message_id": str(record["outbound_message_id_marker"]),
    }


def result(record: dict[str, object], candidate: dict[str, str]) -> str:
    return reconciliation.reconcile_record(
        record, reconciliation.FakeSentMetadataAdapter([candidate]), "automation@test"
    ).state


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        customer = customer_record(directory)
        exact_customer = customer_candidate(customer)
        assert result(customer, exact_customer) == reconciliation.CONFIRMED
        for field in ("from", "to", "subject", "operation_id", "message_fingerprint", "outbound_message_id", "thread_id", "in_reply_to"):
            wrong = exact_customer.copy()
            wrong[field] = "wrong"
            assert result(customer, wrong) == reconciliation.MISMATCH
        missing = exact_customer.copy()
        del missing["thread_id"]
        assert result(customer, missing) == reconciliation.INVALID_METADATA
        assert reconciliation.reconcile_record(customer, reconciliation.FakeSentMetadataAdapter([]), "automation@test").state == reconciliation.NOT_FOUND
        assert reconciliation.reconcile_record(customer, reconciliation.FakeSentMetadataAdapter([exact_customer, exact_customer.copy()]), "automation@test").state == reconciliation.AMBIGUOUS

        # Gmail may replace RFC Message-ID. A legacy intent lacks the new preserved
        # header, but still requires every other strict customer-reply field.
        legacy = customer_record(directory, "incoming-legacy")
        legacy.pop("requires_outbound_id_header")
        changed_id = customer_candidate(legacy)
        changed_id["message_id"] = "<gmail-replaced@test>"
        changed_id["outbound_message_id"] = ""
        assert result(legacy, changed_id) == reconciliation.CONFIRMED
        recipient_subject_only = changed_id.copy()
        recipient_subject_only["operation_id"] = ""
        assert result(legacy, recipient_subject_only) == reconciliation.INVALID_METADATA

        internal = internal_record(directory)
        exact_internal = internal_candidate(internal)
        assert result(internal, exact_internal) == reconciliation.CONFIRMED
        for field in ("to", "subject", "message_fingerprint"):
            wrong = exact_internal.copy()
            wrong[field] = "wrong"
            assert result(internal, wrong) == reconciliation.MISMATCH

        operation = str(customer["operation_id"])
        outbox.transition_intent(operation, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(operation, "fake_timeout", directory=directory)
        adapter = reconciliation.FakeSentMetadataAdapter([exact_customer])
        confirmed = reconciliation.reconcile_outbox_intent(operation, adapter, "automation@test", directory=directory)
        assert confirmed.state == reconciliation.CONFIRMED and adapter.search_count == 1
        reloaded = outbox.load_intent(operation, directory)
        assert reloaded and reloaded["status"] == outbox.SENT_CONFIRMED and reloaded["gmail_message_id"] == "gmail-sent-1"
        rerun = reconciliation.reconcile_outbox_intent(operation, adapter, "automation@test", directory=directory)
        assert rerun.state == reconciliation.CONFIRMED and adapter.search_count == 1

        unresolved = customer_record(directory, "incoming-unresolved")
        unresolved_id = str(unresolved["operation_id"])
        outbox.transition_intent(unresolved_id, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(unresolved_id, "fake_timeout", directory=directory)
        for candidates, expected in (([], reconciliation.NOT_FOUND), ([{**customer_candidate(unresolved), "to": "wrong"}], reconciliation.MISMATCH), ([customer_candidate(unresolved), customer_candidate(unresolved)], reconciliation.AMBIGUOUS)):
            check = reconciliation.reconcile_outbox_intent(unresolved_id, reconciliation.FakeSentMetadataAdapter(candidates), "automation@test", directory=directory)
            assert check.state == expected
            assert outbox.load_intent(unresolved_id, directory)["status"] == outbox.RECONCILIATION_REQUIRED  # type: ignore[index]

        forbidden = {"access_token", "refresh_token", "credentials", "password", "raw", "body", "attachments"}
        assert not (forbidden & set(reloaded))
    print("Gmail Sent reconciliation tests passed: strict evidence, ambiguity, state recovery, and no-send behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
