"""Fake-data tests for Case Results Response ID idempotency; no Google APIs are called."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import case_results_writer as writer


class FakeRequest:
    def __init__(self, execute: Callable[[], dict[str, object]]) -> None:
        self._execute = execute

    def execute(self) -> dict[str, object]:
        return self._execute()


class FakeValues:
    def __init__(self, service: "FakeService") -> None:
        self.service = service

    def get(self, **kwargs: object) -> FakeRequest:
        requested_range = str(kwargs["range"])

        def execute() -> dict[str, object]:
            if requested_range.endswith("!1:1"):
                return {"values": [list(self.service.header)]}
            if requested_range.endswith("!N2:N"):
                return {"values": [[row[-1]] for row in self.service.rows]}
            raise AssertionError(f"Unexpected read range: {requested_range}")

        return FakeRequest(execute)

    def update(self, **kwargs: object) -> FakeRequest:
        requested_range = str(kwargs["range"])

        def execute() -> dict[str, object]:
            if requested_range.endswith("!N1"):
                self.service.header = writer.CASE_RESULTS_HEADERS
                return {}
            raise AssertionError(f"Unexpected update range: {requested_range}")

        return FakeRequest(execute)

    def append(self, **kwargs: object) -> FakeRequest:
        row = list(kwargs["body"]["values"][0])  # type: ignore[index]

        def execute() -> dict[str, object]:
            self.service.append_attempts += 1
            if self.service.append_mode == "timeout_without_write" and self.service.append_attempts == 1:
                raise TimeoutError("fake timeout before write")
            self.service.rows.append(row)
            if self.service.append_mode == "timeout_after_write" and self.service.append_attempts == 1:
                raise TimeoutError("fake timeout after write")
            return {}

        return FakeRequest(execute)


class FakeSpreadsheets:
    def __init__(self, service: "FakeService") -> None:
        self.service = service

    def get(self, **kwargs: object) -> FakeRequest:
        return FakeRequest(lambda: {"sheets": [{"properties": {"title": writer.CASE_RESULTS_TAB}}]})

    def values(self) -> FakeValues:
        return FakeValues(self.service)


class FakeService:
    def __init__(self, header: tuple[str, ...] = writer.CASE_RESULTS_HEADERS) -> None:
        self.header = header
        self.rows: list[list[object]] = []
        self.append_attempts = 0
        self.append_mode = "normal"

    def spreadsheets(self) -> FakeSpreadsheets:
        return FakeSpreadsheets(self)


def fake_retry(operation: Callable[[], bool | dict[str, object]], **_: object) -> bool | dict[str, object]:
    for attempt in range(2):
        try:
            return operation()
        except TimeoutError:
            if attempt:
                raise
    raise AssertionError("Unreachable retry state")


def form_fields() -> dict[str, str]:
    return {header: f"value-{index}" for index, header in enumerate(writer.FORM_FIELD_HEADERS)}


def child_lock_attempt(lock_path: Path) -> subprocess.CompletedProcess[str]:
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, r'C:\\Mail\\src'); "
        "from case_results_writer import case_results_write_lock, CaseResultsLockUnavailableError; "
        f"path = Path({str(lock_path)!r}); "
        "\ntry:\n with case_results_write_lock(path): pass\nexcept CaseResultsLockUnavailableError: raise SystemExit(1)\n"
    )
    return subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, check=False)


def main() -> int:
    original_retry = writer.retry_call
    writer.retry_call = fake_retry  # type: ignore[assignment]
    try:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "case-results.lock"
            fields = form_fields()

            service = FakeService()
            assert writer.append_case_result(service, fields, ["Open"], "id-one", lock_path)
            assert not writer.append_case_result(service, fields, ["Open"], "id-one", lock_path)
            assert len(service.rows) == 1

            assert writer.append_case_result(service, fields, ["Open"], "id-two", lock_path)
            assert len(service.rows) == 2

            legacy = FakeService(header=writer.LEGACY_CASE_RESULTS_HEADERS)
            legacy.rows.append(["legacy"] * 13 + [""])
            writer.ensure_case_results_tab(legacy)
            assert legacy.header == writer.CASE_RESULTS_HEADERS
            assert writer.append_case_result(legacy, fields, [], "id-legacy-new", lock_path)
            assert len(legacy.rows) == 2

            timeout_after_write = FakeService()
            timeout_after_write.append_mode = "timeout_after_write"
            assert not writer.append_case_result(timeout_after_write, fields, [], "id-timeout-written", lock_path)
            assert timeout_after_write.append_attempts == 1 and len(timeout_after_write.rows) == 1

            timeout_without_write = FakeService()
            timeout_without_write.append_mode = "timeout_without_write"
            assert writer.append_case_result(timeout_without_write, fields, [], "id-timeout-retry", lock_path)
            assert timeout_without_write.append_attempts == 2 and len(timeout_without_write.rows) == 1

            crash_recovery = FakeService()
            assert writer.append_case_result(crash_recovery, fields, [], "id-crash", lock_path)
            assert not writer.append_case_result(crash_recovery, fields, [], "id-crash", lock_path)
            assert len(crash_recovery.rows) == 1

            with writer.case_results_write_lock(lock_path):
                blocked = child_lock_attempt(lock_path)
                assert blocked.returncode == 1 and not blocked.stderr
            with writer.case_results_write_lock(lock_path):
                pass
            try:
                with writer.case_results_write_lock(lock_path):
                    raise RuntimeError("fake protected-operation failure")
            except RuntimeError:
                pass
            with writer.case_results_write_lock(lock_path):
                pass
    finally:
        writer.retry_call = original_retry  # type: ignore[assignment]
    print("Case Results Response ID tests passed: deduplication, legacy rows, timeout recovery, crash recovery, and locking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
