"""Local-only configuration tests using isolated fake .env files; no API access occurs."""

from __future__ import annotations

import tempfile
from pathlib import Path

from config import REQUIRED_KEYS, load_config
from portal_db import mysql_options, portal_database_name, source_database_name, validate_test_mysql_host


def fake_env_text() -> str:
    return "\n".join(["GMAIL_ACCOUNT=test@example.com", "INTERNAL_NOTIFICATION_RECIPIENT=internal@example.com", "GOOGLE_FORM_URL=https://example.com/form", "FORM_RESPONSE_SPREADSHEET_ID=form-sheet", "CASES_SPREADSHEET_ID=cases-sheet", "CASES_SHEET_TAB=Cases", "CASE_RESULTS_TAB=Results", "GMAIL_MAX_AGE_HOURS=24", "GMAIL_BATCH_SIZE=10"])


def main() -> int:
    # These assertions exercise only pure validation; no database connection is opened.
    validate_test_mysql_host("127.0.0.1")
    try:
        validate_test_mysql_host("example.aivencloud.com")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Aiven host was not rejected before database access")
    test_db_options = mysql_options(pool=False)
    assert (
        test_db_options["host"] == "127.0.0.1"
        and test_db_options["port"] == 3306
        and test_db_options["database"] == "durafit_portal_test"
    )
    assert portal_database_name() == "durafit_portal_test"
    try:
        source_database_name("crm")
    except RuntimeError as error:
        assert "fixture database" in str(error)
    else:
        raise AssertionError("Unconfigured test CRM source fixture was not guarded")
    with tempfile.TemporaryDirectory() as directory:
        env_path = Path(directory) / ".env"
        env_path.write_text(fake_env_text(), encoding="utf-8")
        config = load_config(env_path, environment={})
        assert (
            config.app_env == "test"
            and config.gmail_account == "test@example.com"
            and config.cases_sheet_tab == "Cases"
            and config.gmail_max_age_hours == 24
            and config.gmail_batch_size == 10
        )
        env_path.write_text("GMAIL_ACCOUNT=test@example.com\n", encoding="utf-8")
        try:
            load_config(env_path, environment={})
        except ValueError as error:
            assert "Missing required configuration" in str(error)
        else:
            raise AssertionError("Missing configuration did not raise a clear error")
    gitignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore and ".env.*" in gitignore and REQUIRED_KEYS
    print("Configuration self-test passed: local MySQL accepted, Aiven rejected before access, and config checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
