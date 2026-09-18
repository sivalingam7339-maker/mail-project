"""Local fake-data tests for send_outbox; no Gmail, Sheets, or network access."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import send_outbox as outbox


def child_lock_attempt(directory: Path) -> subprocess.CompletedProcess[str]:
    code = (
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, r'C:\\Mail\\src')\n"
        "from send_outbox import outbox_lock, OutboxLockUnavailableError\n"
        f"directory = Path({str(directory)!r})\n"
        "try:\n    with outbox_lock(directory):\n        pass\n"
        "except OutboxLockUnavailableError:\n    raise SystemExit(1)\n"
    )
    return subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, check=False)


def customer_intent(directory: Path, source_message_id: str = "gmail-source-1") -> dict[str, object]:
    return outbox.create_customer_reply_intent(
        source_message_id=source_message_id,
        source_rfc_message_id="<incoming@example.test>",
        source_thread_id="thread-1",
        recipient="customer@example.test",
        subject="Need help with my order",
        intended_content="Please complete the support form.",
        directory=directory,
    )


def metadata(record: dict[str, object]) -> dict[str, str]:
    return {
        "from": "automation@example.test",
        "to": "customer@example.test",
        "subject": "Need help with my order",
        "thread_id": "thread-1",
        "in_reply_to": "<incoming@example.test>",
        "message_id": str(record["outbound_rfc_message_id"]),
        "outbound_message_id": str(record["outbound_message_id_marker"]),
        "operation_id": str(record["operation_id"]),
        "message_fingerprint": str(record["message_fingerprint"]),
    }


def main() -> int:
    assert outbox.customer_reply_operation_id("m") == outbox.customer_reply_operation_id("m")
    assert outbox.internal_notification_operation_id("r") == outbox.internal_notification_operation_id("r")
    assert outbox.customer_reply_operation_id("m") != outbox.customer_reply_operation_id("n")
    assert outbox.outbound_rfc_message_id("operation") == outbox.outbound_rfc_message_id("operation")
    assert outbox.recipient_fingerprint("Recipient") == outbox.recipient_fingerprint("recipient")
    assert outbox.message_fingerprint("a@test", "Subject", "Body", "op") == outbox.message_fingerprint("a@test", "Subject", "Body", "op")

    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        first = customer_intent(directory)
        same = customer_intent(directory)
        different = customer_intent(directory, "gmail-source-2")
        assert first["operation_id"] == same["operation_id"] and len(list(directory.glob("*.json"))) == 2
        assert different["operation_id"] != first["operation_id"]
        saved_path = outbox.record_path(str(first["operation_id"]), directory)
        assert json.loads(saved_path.read_text(encoding="utf-8"))["operation_id"] == first["operation_id"]
        saved_path.with_suffix(".tmp").write_text("{incomplete", encoding="utf-8")
        assert outbox.load_intent(str(first["operation_id"]), directory)["status"] == outbox.PENDING

        sending = outbox.transition_intent(str(first["operation_id"]), outbox.SENDING, directory=directory)
        assert sending["attempt_count"] == 1 and not outbox.may_send(sending)
        required = outbox.mark_reconciliation_required(str(first["operation_id"]), "timeout", directory=directory)
        assert required["status"] == outbox.RECONCILIATION_REQUIRED and not outbox.may_send(required)
        try:
            outbox.transition_intent(str(first["operation_id"]), outbox.SENDING, directory=directory)
        except ValueError:
            pass
        else:
            raise AssertionError("Reconciliation-required intent was incorrectly eligible for send.")

        sent = customer_intent(directory, "gmail-source-sent")
        outbox.transition_intent(str(sent["operation_id"]), outbox.SENDING, directory=directory)
        confirmed = outbox.mark_send_confirmed(str(sent["operation_id"]), "sent-id", "thread-1", directory=directory)
        assert not outbox.may_send(confirmed)
        recorded = outbox.mark_ledger_recorded(str(sent["operation_id"]), directory=directory)
        assert recorded["status"] == outbox.LEDGER_RECORDED and outbox.load_intent(str(sent["operation_id"]), directory)["ledger_recorded"]

        candidate = customer_intent(directory, "gmail-source-reconcile")
        assert outbox.customer_reply_metadata_matches(candidate, metadata(candidate), "automation@example.test")
        for changed in ("thread_id", "to", "in_reply_to", "outbound_message_id"):
            wrong = metadata(candidate)
            wrong[changed] = "wrong"
            assert not outbox.customer_reply_metadata_matches(candidate, wrong, "automation@example.test")

        internal = outbox.create_internal_notification_intent(
            response_id="response-1",
            recipient="internal@example.test",
            subject="New Customer Case - order-1",
            intended_content="Case notification summary",
            directory=directory,
        )
        internal_metadata = {
            "from": "automation@example.test", "to": "internal@example.test",
            "subject": "New Customer Case - order-1", "message_id": str(internal["outbound_rfc_message_id"]),
            "outbound_message_id": str(internal["outbound_message_id_marker"]),
            "operation_id": str(internal["operation_id"]), "message_fingerprint": str(internal["message_fingerprint"]),
        }
        assert outbox.internal_notification_metadata_matches(internal, internal_metadata, "automation@example.test")
        for changed in ("to", "subject", "message_fingerprint", "outbound_message_id"):
            wrong = internal_metadata.copy()
            wrong[changed] = "wrong"
            assert not outbox.internal_notification_metadata_matches(internal, wrong, "automation@example.test")
        forbidden = {"access_token", "refresh_token", "oauth", "raw", "body", "attachments", "invoice", "image"}
        assert not (forbidden & set(internal)) and "intended_content" not in internal

        with outbox.outbox_lock(directory):
            blocked = child_lock_attempt(directory)
            assert blocked.returncode == 1 and not blocked.stderr
        with outbox.outbox_lock(directory):
            pass
        try:
            with outbox.outbox_lock(directory):
                raise RuntimeError("fake failure")
        except RuntimeError:
            pass
        with outbox.outbox_lock(directory):
            pass
    print("Send outbox tests passed: IDs, atomic records, state safety, locks, and fake reconciliation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
