"""Fake-only tests for the live-read-only adapter; no OAuth or Gmail calls occur."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import gmail_sent_live_adapter as live
import gmail_sent_reconciliation as reconciliation
import send_outbox as outbox


class FakeRequest:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value

    def execute(self) -> dict[str, object]:
        return self.value


class FakeMessages:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self.messages = messages
        self.list_calls = 0
        self.get_calls = 0
        self.query = ""

    def list(self, **kwargs: object) -> FakeRequest:
        self.list_calls += 1
        self.query = str(kwargs["q"])
        return FakeRequest({"messages": [{"id": item["id"]} for item in self.messages]})

    def get(self, **kwargs: object) -> FakeRequest:
        self.get_calls += 1
        item = next(message for message in self.messages if message["id"] == kwargs["id"])
        return FakeRequest(item)


class FakeUsers:
    def __init__(self, account: str, messages: list[dict[str, object]]) -> None:
        self.account = account
        self.messages_api = FakeMessages(messages)
        self.profile_calls = 0

    def getProfile(self, **_: object) -> FakeRequest:
        self.profile_calls += 1
        return FakeRequest({"emailAddress": self.account})

    def messages(self) -> FakeMessages:
        return self.messages_api


class FakeService:
    def __init__(self, account: str, messages: list[dict[str, object]]) -> None:
        self.users_api = FakeUsers(account, messages)

    def users(self) -> FakeUsers:
        return self.users_api


def fake_message(message_id: str = "<cca-test@customer-case-automation.local>") -> dict[str, object]:
    return {
        "id": "gmail-1", "threadId": "thread-1",
        "payload": {"headers": [
            {"name": "From", "value": "automation@test"}, {"name": "To", "value": "customer@test"},
            {"name": "Subject", "value": "Re: Help"}, {"name": "Message-ID", "value": message_id},
            {"name": "In-Reply-To", "value": "<incoming@test>"},
            {"name": "X-Customer-Case-Operation-ID", "value": "customer_reply:v1:incoming"},
            {"name": "X-Customer-Case-Message-Fingerprint", "value": "fingerprint"},
            {"name": "X-Customer-Case-Outbound-Message-ID", "value": "outbound-marker"},
        ]},
    }


def main() -> int:
    original_argv = sys.argv
    try:
        sys.argv = ["adapter"]
        assert live.main() == 0
        sys.argv = ["adapter", "--live-read-only"]
        assert live.main() == 2
        sys.argv = ["adapter", "--live-read-only", "--message-id", "not-a-message-id"]
        assert live.main() == 2
    finally:
        sys.argv = original_argv

    service = FakeService("sivalingam7339@gmail.com", [])
    live.verify_test_account(service)
    try:
        live.verify_test_account(FakeService("wrong@example.test", []))
    except ValueError:
        pass
    else:
        raise AssertionError("Wrong account was not blocked")

    adapter = live.GmailSentLiveAdapter(FakeService("sivalingam7339@gmail.com", []))
    assert adapter.find_sent_messages_by_message_id("<cca-test@customer-case-automation.local>") == []
    one_service = FakeService("sivalingam7339@gmail.com", [fake_message()])
    one = live.GmailSentLiveAdapter(one_service)
    candidates = one.find_sent_messages_by_message_id("<cca-test@customer-case-automation.local>")
    assert len(candidates) == 1 and one_service.users_api.messages_api.query == "in:sent rfc822msgid:<cca-test@customer-case-automation.local>"
    multiple = live.GmailSentLiveAdapter(FakeService("sivalingam7339@gmail.com", [fake_message(), {**fake_message(), "id": "gmail-2"}]))
    assert len(multiple.find_sent_messages_by_message_id("<cca-test@customer-case-automation.local>")) == 2
    try:
        one.find_sent_messages_by_message_id("subject:wrong")
    except ValueError:
        pass
    else:
        raise AssertionError("Non-Message-ID search was not blocked")
    assert not hasattr(one, "send") and not hasattr(one, "modify") and not hasattr(one, "delete")

    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        record = outbox.create_customer_reply_intent(
            source_message_id="incoming", source_rfc_message_id="<incoming@test>", source_thread_id="thread-1",
            recipient="customer@test", subject="Re: Help", intended_content="body", directory=directory,
        )
        operation = str(record["operation_id"])
        outbox.transition_intent(operation, outbox.SENDING, directory=directory)
        outbox.mark_reconciliation_required(operation, "fake", directory=directory)
        candidate = {
            "gmail_message_id": "gmail-1", "thread_id": "thread-1", "from": "automation@test", "to": "customer@test",
            "subject": "Re: Help", "message_id": str(record["outbound_rfc_message_id"]), "operation_id": operation,
            "message_fingerprint": str(record["message_fingerprint"]), "outbound_message_id": str(record["outbound_message_id_marker"]), "in_reply_to": "<incoming@test>",
        }
        result = live.reconcile_existing_intent_read_only(
            operation, reconciliation.FakeSentMetadataAdapter([candidate]), "automation@test", directory=directory
        )
        assert result.state == reconciliation.CONFIRMED
        assert outbox.load_intent(operation, directory)["status"] == outbox.RECONCILIATION_REQUIRED  # type: ignore[index]
    print("Live Sent adapter fake tests passed: guards, metadata-only lookup, and read-only reconciliation helper.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
