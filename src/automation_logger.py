"""Central, privacy-conscious rotating file logging for automation orchestration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIRECTORY = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIRECTORY / "automation.log"
MAX_LOG_BYTES = 1_048_576  # 1 MiB
BACKUP_COUNT = 3
LOGGER_NAME = "customer_case_automation"


def get_automation_logger() -> logging.Logger:
    """Return the singleton rotating logger without emitting sensitive workflow data."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
