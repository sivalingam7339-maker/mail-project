"""Fake-data retry tests; this module never contacts Gmail or Google APIs."""

from __future__ import annotations

from retry_utils import MAX_ATTEMPTS, retry_call


class FakeTransientError(Exception):
    status_code = 503


def main() -> int:
    delays: list[float] = []
    attempts = 0

    def succeeds_on_third_attempt() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise FakeTransientError()
        return "success"

    assert retry_call(
        succeeds_on_third_attempt,
        operation_name="fake_transient_success",
        sleep=delays.append,
    ) == "success"
    assert attempts == 3 and delays == [1.0, 2.0]

    permanent_attempts = 0

    def permanent_failure() -> None:
        nonlocal permanent_attempts
        permanent_attempts += 1
        raise ValueError("fake malformed data")

    try:
        retry_call(permanent_failure, operation_name="fake_permanent", sleep=delays.append)
    except ValueError:
        pass
    else:
        raise AssertionError("Permanent error was not raised")
    assert permanent_attempts == 1

    exhausted_attempts = 0

    def always_transient() -> None:
        nonlocal exhausted_attempts
        exhausted_attempts += 1
        raise FakeTransientError()

    try:
        retry_call(always_transient, operation_name="fake_exhausted", sleep=lambda _: None)
    except FakeTransientError:
        pass
    else:
        raise AssertionError("Transient error was not raised after maximum attempts")
    assert exhausted_attempts == MAX_ATTEMPTS
    print("Retry self-test passed: transient retry, exponential backoff, permanent skip, and attempt limit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
