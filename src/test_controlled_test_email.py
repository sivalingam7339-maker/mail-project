"""Local fake tests for isolated controlled_test_email; no Gmail API client is used."""

from __future__ import annotations

import base64
import tempfile
from email import message_from_bytes
from pathlib import Path

import controlled_test_email as test_email
import send_outbox as outbox


class FakeService:
    pass


def main() -> int:
    account = test_email.EXPECTED_ACCOUNT.casefold()
    for kwargs in (
        {"account": "wrong@test", "recipient": test_email.EXPECTED_ACCOUNT, "operation_id": test_email.OPERATION_ID, "subject": test_email.SUBJECT, "confirm_send": True},
        {"account": account, "recipient": "wrong@test", "operation_id": test_email.OPERATION_ID, "subject": test_email.SUBJECT, "confirm_send": True},
        {"account": account, "recipient": test_email.EXPECTED_ACCOUNT, "operation_id": "wrong", "subject": test_email.SUBJECT, "confirm_send": True},
        {"account": account, "recipient": test_email.EXPECTED_ACCOUNT, "operation_id": test_email.OPERATION_ID, "subject": "wrong", "confirm_send": True},
        {"account": account, "recipient": test_email.EXPECTED_ACCOUNT, "operation_id": test_email.OPERATION_ID, "subject": test_email.SUBJECT, "confirm_send": False},
    ):
        try:
            test_email.validate_guards(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("A controlled-send guard did not block invalid input.")

    preview_one = test_email.preview(account, test_email.EXPECTED_ACCOUNT)
    preview_two = test_email.preview(account, test_email.EXPECTED_ACCOUNT)
    assert preview_one == preview_two
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        payloads: list[dict[str, str]] = []

        def successful_send(payload: dict[str, str]) -> dict[str, str]:
            intent = outbox.load_intent(test_email.OPERATION_ID, directory)
            assert intent and intent["status"] == outbox.SENDING
            payloads.append(payload)
            return {"id": "gmail-controlled", "threadId": "thread-controlled"}

        outcome = test_email.run_controlled_send(
            FakeService(), account, confirm_send=True, send_callable=successful_send, outbox_directory=directory
        )
        assert outcome.status == outbox.SENT_CONFIRMED and len(payloads) == 1
        email = message_from_bytes(base64.urlsafe_b64decode(payloads[0]["raw"]))
        record = outbox.load_intent(test_email.OPERATION_ID, directory)
        assert email["Message-ID"] == record["outbound_rfc_message_id"]
        assert email["X-Customer-Case-Operation-ID"] == test_email.OPERATION_ID
        assert email["X-Customer-Case-Message-Fingerprint"] == record["message_fingerprint"]
        assert "Order ID" not in email.get_payload(decode=True).decode("utf-8")
        assert test_email.run_controlled_send(
            FakeService(), account, confirm_send=True,
            send_callable=lambda _: (_ for _ in ()).throw(AssertionError("duplicate send")), outbox_directory=directory,
        ).status == outbox.SENT_CONFIRMED

        uncertain_dir = directory / "uncertain"
        uncertain = test_email.run_controlled_send(
            FakeService(), account, confirm_send=True,
            send_callable=lambda _: (_ for _ in ()).throw(TimeoutError("fake")), outbox_directory=uncertain_dir,
        )
        assert uncertain.status == outbox.RECONCILIATION_REQUIRED
        assert test_email.run_controlled_send(
            FakeService(), account, confirm_send=True,
            send_callable=lambda _: (_ for _ in ()).throw(AssertionError("must not resend")), outbox_directory=uncertain_dir,
        ).status == outbox.RECONCILIATION_REQUIRED
        forbidden = {"access_token", "refresh_token", "credentials", "password", "raw", "body", "attachments", "invoice", "image"}
        assert not (forbidden & set(record))
    print("Controlled test email local tests passed: guards, one-send state, headers, uncertainty, and no ledger coupling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
