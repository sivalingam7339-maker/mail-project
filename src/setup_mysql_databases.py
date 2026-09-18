"""Create and migrate the isolated MySQL data stores from the SQLite backups.

This script does not access the React application, customer portal, dashboard,
or Gmail automation. Credentials are read exclusively from environment values.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import mysql.connector


ROOT = Path(__file__).resolve().parent.parent
DATABASES = {
    "crm": os.environ.get("CRM_DATABASE", "crm_database"),
    "cases": os.environ.get("CASES_DATABASE", "cases_database"),
    "submissions": os.environ.get("SUBMISSIONS_DATABASE", "customer_submissions_database"),
}
SQLITE_SOURCES = {
    "crm": (ROOT / "databases" / "crm_database.sqlite3", "crm_records"),
    "cases": (ROOT / "databases" / "cases_database.sqlite3", "case_records"),
}


def mysql_connection(database: str | None = None):
    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    options = {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ["MYSQL_PORT"]),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if database:
        options["database"] = database
    return mysql.connector.connect(**options)


def quote(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def sqlite_columns(source: Path, table: str) -> list[str]:
    with sqlite3.connect(source) as connection:
        return [row[1] for row in connection.execute(f"PRAGMA table_info({quote(table)})")]


def create_databases() -> None:
    connection = mysql_connection()
    try:
        cursor = connection.cursor()
        for name in DATABASES.values():
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote(name)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
        connection.commit()
    finally:
        connection.close()


def create_source_table(kind: str) -> list[str]:
    source, table = SQLITE_SOURCES[kind]
    columns = sqlite_columns(source, table)
    order_id = next((column for column in columns if column.strip().casefold() == "order id"), None)
    if not order_id:
        raise RuntimeError(f"No exact Order ID column found in {source}")
    definitions = [
        f"{quote(column)} VARCHAR(255) NULL" if column == order_id else f"{quote(column)} TEXT NULL"
        for column in columns
    ]
    connection = mysql_connection(DATABASES[kind])
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {quote(table)} ({', '.join(definitions)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
        index_name = "ux_crm_order_id" if kind == "crm" else "ix_cases_order_id"
        unique = "UNIQUE " if kind == "crm" else ""
        cursor.execute(
            f"CREATE {unique}INDEX {quote(index_name)} ON {quote(table)} ({quote(order_id)})"
        )
        connection.commit()
    except mysql.connector.Error as error:
        # MySQL error 1061 means the desired index already exists, so reruns are safe.
        if error.errno != 1061:
            raise
    finally:
        connection.close()
    return columns


def migrate_source_table(kind: str, columns: list[str]) -> int:
    source, table = SQLITE_SOURCES[kind]
    order_id = next(column for column in columns if column.strip().casefold() == "order id")
    connection = mysql_connection(DATABASES[kind])
    inserted = 0
    try:
        cursor = connection.cursor()
        column_list = ", ".join(quote(column) for column in columns)
        placeholders = ", ".join("%s" for _ in columns)
        update_clause = ", ".join(f"{quote(column)}={quote(column)}" for column in columns if column != order_id)
        statement = (
            f"INSERT INTO {quote(table)} ({column_list}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )
        with sqlite3.connect(source) as sqlite_connection:
            rows = sqlite_connection.execute(f"SELECT {column_list} FROM {quote(table)}")
            batch: list[tuple[object, ...]] = []
            for row in rows:
                batch.append(tuple(row))
                if len(batch) == 500:
                    cursor.executemany(statement, batch)
                    inserted += len(batch)
                    batch.clear()
            if batch:
                cursor.executemany(statement, batch)
                inserted += len(batch)
        connection.commit()
    finally:
        connection.close()
    return inserted


def create_customer_submissions_table() -> None:
    connection = mysql_connection(DATABASES["submissions"])
    try:
        cursor = connection.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS customer_submissions (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                order_id VARCHAR(255) NULL,
                cx_number VARCHAR(255) NULL,
                issue_description TEXT NULL,
                invoice_file_path TEXT NULL,
                state VARCHAR(255) NULL,
                pincode VARCHAR(32) NULL,
                complete_address TEXT NULL,
                product_images TEXT NULL,
                additional_remarks TEXT NULL,
                customer_email VARCHAR(320) NULL,
                so_owner VARCHAR(255) NULL,
                crm_order_found BOOLEAN NULL,
                existing_case_found BOOLEAN NULL,
                existing_case_count INT UNSIGNED NULL,
                case_created BOOLEAN NULL,
                case_id VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id), INDEX ix_customer_submissions_order_id (order_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    create_databases()
    crm_columns = create_source_table("crm")
    cases_columns = create_source_table("cases")
    crm_rows = migrate_source_table("crm", crm_columns)
    cases_rows = migrate_source_table("cases", cases_columns)
    create_customer_submissions_table()
    print(f"CRM rows processed: {crm_rows}; Cases rows processed: {cases_rows}")


if __name__ == "__main__":
    main()
