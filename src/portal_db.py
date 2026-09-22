"""Server-side, read-only MySQL access for the customer portal."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator

import mysql.connector
from mysql.connector import pooling


PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Local configuration is a development fallback; deployed services use environment variables.
ENV_FILES = (PROJECT_ROOT / ".env",)
POOL_NAME = "durafit_portal_readonly"
_pool: pooling.MySQLConnectionPool | None = None


def _read_local_env() -> dict[str, str]:
    """Read configuration without printing any values or secrets."""
    values: dict[str, str] = {}
    for path in ENV_FILES:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def mysql_options(database: str = "durafit_crm", pool: bool = True) -> dict[str, object]:
    values = _read_local_env()
    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError("Missing required local MySQL configuration.")
    options: dict[str, object] = {
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
