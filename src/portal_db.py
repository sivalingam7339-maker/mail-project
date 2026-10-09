"""Server-side, read-only MySQL access for the customer portal."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Iterator

import mysql.connector
from mysql.connector import pooling


PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Local configuration is a development fallback; deployed services use environment variables.
ENV_FILES = (PROJECT_ROOT / ".env",)
TEST_ENV_FILE = PROJECT_ROOT / ".env.test"
LOCAL_TEST_MYSQL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PRODUCTION_PORTAL_DATABASE = "durafit_portal"
TEST_PORTAL_DATABASE = "durafit_portal_test"
POOL_NAME = "durafit_portal_readonly"
_pool: pooling.MySQLConnectionPool | None = None


def _is_test_process() -> bool:
    """Return whether this process is executing a Python test module."""
    return (
        "unittest" in sys.modules
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
        or Path(sys.argv[0]).name.startswith("test")
    )


def validate_test_mysql_host(host: str) -> None:
    """Reject every non-local MySQL host before a test can open a connection."""
    normalized = host.strip().casefold().strip("[]")
    if normalized not in LOCAL_TEST_MYSQL_HOSTS:
        raise RuntimeError(
            "Unsafe test MySQL host rejected before database access. "
            "Tests may use only localhost, 127.0.0.1, or ::1."
        )


def _read_local_env() -> dict[str, str]:
    """Read configuration without printing any values or secrets."""
    values: dict[str, str] = {}
    def load_file(path: Path) -> None:
        if not path.is_file():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()

    for path in ENV_FILES:
        load_file(path)
    values.update({key: value for key, value in os.environ.items() if value})
    if _is_test_process() or values.get("APP_ENV", "").strip().casefold() == "test":
        values["MYSQL_PASSWORD"] = os.environ.get("MYSQL_TEST_PASSWORD", "")
        load_file(TEST_ENV_FILE)
        values["MYSQL_HOST"] = "127.0.0.1"
        values["MYSQL_PORT"] = "3306"
        values["MYSQL_USER"] = "root"
        values["MYSQL_DATABASE"] = TEST_PORTAL_DATABASE
        values["MYSQL_SSL_REQUIRED"] = "false"
    return values


def _is_test_environment(values: dict[str, str]) -> bool:
    return _is_test_process() or values.get("APP_ENV", "").strip().casefold() == "test"


def portal_database_name(values: dict[str, str] | None = None) -> str:
    """Return the application-owned portal database for this environment."""
    values = _read_local_env() if values is None else values
    if _is_test_environment(values):
        validate_test_mysql_host(values.get("MYSQL_HOST", "127.0.0.1"))
        return TEST_PORTAL_DATABASE
    return PRODUCTION_PORTAL_DATABASE


def source_database_name(kind: str, values: dict[str, str] | None = None) -> str:
    """Return a source database, requiring an explicit local fixture in test mode."""
    if kind not in {"crm", "cases"}:
        raise ValueError("Unknown source database")
    values = _read_local_env() if values is None else values
    if _is_test_environment(values):
        validate_test_mysql_host(values.get("MYSQL_HOST", "127.0.0.1"))
        key = f"MYSQL_TEST_{kind.upper()}_DATABASE"
        database = values.get(key, "").strip()
        if not database:
            raise RuntimeError(f"Local test {kind.upper()} fixture database is not configured; workflow skipped before database access.")
        return database
    return "durafit_crm" if kind == "crm" else "durafit_cases"


def mysql_options(database: str = "durafit_crm", pool: bool = True) -> dict[str, object]:
    values = _read_local_env()
    if _is_test_environment(values):
        # This check happens before mysql.connector receives any options.
        validate_test_mysql_host(values.get("MYSQL_HOST", "127.0.0.1"))
        local_sources = {
            values.get("MYSQL_TEST_CRM_DATABASE", "").strip(),
            values.get("MYSQL_TEST_CASES_DATABASE", "").strip(),
        } - {""}
        target_db = database if database in local_sources else TEST_PORTAL_DATABASE
        options: dict[str, object] = {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": values.get("MYSQL_PASSWORD", ""),
            "database": target_db,
            "charset": "utf8mb4",
            "use_unicode": True,
            "autocommit": True,
        }
        if pool:
            options.update({"pool_name": POOL_NAME, "pool_size": 5, "pool_reset_session": True})
        return options
    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError("Missing required local MySQL configuration.")
    options = {
        "host": values["MYSQL_HOST"],
        "port": int(values["MYSQL_PORT"]),
        "user": values["MYSQL_USER"],
        "password": values["MYSQL_PASSWORD"],
        "database": database,
        "charset": "utf8mb4",
        "use_unicode": True,
        "autocommit": True,
    }
    if values.get("MYSQL_SSL_REQUIRED", "").casefold() == "true":
        options["ssl_disabled"] = False
    if pool:
        options.update({"pool_name": POOL_NAME, "pool_size": 5, "pool_reset_session": True})
    return options


def _connection_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(**mysql_options())
    return _pool


@contextmanager
def connection() -> Iterator[mysql.connector.MySQLConnection]:
    """Yield a pooled connection and always return it to the pool."""
    conn = _connection_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


def find_order(order_id: str) -> dict[str, str | None] | None:
    """Look up one CRM order using a parameterized, read-only query."""
    query = """
        SELECT `Order ID`, `Name`, `Account Name`, `Product Type`, `Product Name`, `Order Date`, `Place of Supply`,
               `Purchased Product`, `SKU new`, `Mobile Number`, `Customer Email`
        FROM `durafit_crm`.`crm_records`
        WHERE `Order ID` = %s
        LIMIT 1
    """
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, (order_id,))
            return cursor.fetchone()
        finally:
            cursor.close()


def close_pool() -> None:
    """Close idle pooled connections during application shutdown."""
    global _pool
    if _pool is not None:
        _pool._remove_connections()  # mysql-connector's pool cleanup API
        _pool = None
