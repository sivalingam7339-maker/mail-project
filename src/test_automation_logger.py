"""Local-only verification for automation logging; it never runs any workflow."""

from __future__ import annotations

from logging.handlers import RotatingFileHandler

from automation_logger import BACKUP_COUNT, LOG_DIRECTORY, LOG_FILE, MAX_LOG_BYTES, get_automation_logger


def main() -> int:
    logger = get_automation_logger()
    logger.info("LOGGER_SELF_TEST local logging verification")
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            assert handler.maxBytes == MAX_LOG_BYTES
            assert handler.backupCount == BACKUP_COUNT
            break
    else:
        raise AssertionError("RotatingFileHandler was not configured")
    assert LOG_DIRECTORY.is_dir()
    assert LOG_FILE.is_file()
    assert "LOGGER_SELF_TEST local logging verification" in LOG_FILE.read_text(encoding="utf-8")
    print(f"Logging self-test passed: {LOG_FILE}")
    print(f"Rotation: {MAX_LOG_BYTES} bytes, {BACKUP_COUNT} backup files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
