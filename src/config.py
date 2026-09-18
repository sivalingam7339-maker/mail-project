"""Load non-secret environment configuration from the project's local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_KEYS = frozenset({"GMAIL_ACCOUNT", "INTERNAL_NOTIFICATION_RECIPIENT", "GOOGLE_FORM_URL", "FORM_RESPONSE_SPREADSHEET_ID", "CASES_SPREADSHEET_ID", "CASES_SHEET_TAB", "CASE_RESULTS_TAB", "GMAIL_MAX_AGE_HOURS", "GMAIL_BATCH_SIZE"})


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    gmail_account: str
    internal_notification_recipient: str
    google_form_url: str
    form_response_spreadsheet_id: str
    cases_spreadsheet_id: str
    cases_sheet_tab: str
    case_results_tab: str
    gmail_max_age_hours: int
    gmail_batch_size: int


def read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE settings without printing or loading any secrets."""
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid configuration line {line_number} in {path.name}")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key:
            raise ValueError(f"Empty configuration key on line {line_number} in {path.name}")
        values[key] = value
    return values


def load_config(env_file: Path = ENV_FILE, environment: Mapping[str, str] | None = None) -> AppConfig:
    """Load TEST by default; process environment variables may override non-secret settings."""
    values = read_env_file(env_file)
    overrides = os.environ if environment is None else environment
    values.update({key: value for key, value in overrides.items() if key in REQUIRED_KEYS or key == "APP_ENV"})
    missing = sorted(key for key in REQUIRED_KEYS if not values.get(key, "").strip())
    if missing:
        raise ValueError("Missing required configuration: " + ", ".join(missing))
    try:
        max_age_hours = int(values["GMAIL_MAX_AGE_HOURS"])
        batch_size = int(values["GMAIL_BATCH_SIZE"])
    except ValueError as error:
        raise ValueError("GMAIL_MAX_AGE_HOURS and GMAIL_BATCH_SIZE must be integers.") from error
    if max_age_hours < 1 or batch_size < 1:
        raise ValueError("GMAIL_MAX_AGE_HOURS and GMAIL_BATCH_SIZE must be positive.")
    return AppConfig(
        app_env=values.get("APP_ENV", "test").strip().casefold() or "test",
        gmail_account=values["GMAIL_ACCOUNT"].strip(),
        internal_notification_recipient=values["INTERNAL_NOTIFICATION_RECIPIENT"].strip(),
        google_form_url=values["GOOGLE_FORM_URL"].strip(),
        form_response_spreadsheet_id=values["FORM_RESPONSE_SPREADSHEET_ID"].strip(),
        cases_spreadsheet_id=values["CASES_SPREADSHEET_ID"].strip(),
        cases_sheet_tab=values["CASES_SHEET_TAB"].strip(),
        case_results_tab=values["CASE_RESULTS_TAB"].strip(),
        gmail_max_age_hours=max_age_hours,
        gmail_batch_size=batch_size,
    )


CONFIG = load_config()
