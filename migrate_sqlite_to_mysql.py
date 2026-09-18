"""One-time, read-only SQLite to MySQL migration for the Durafit CRM/Cases data."""
from pathlib import Path
import os
import sqlite3
import mysql.connector

ROOT = Path(r"C:\Mail")
SOURCES = {
    "durafit_crm": (ROOT / "databases" / "crm_database.sqlite3", ["crm_records", "imported_record_hashes"]),
    "durafit_cases": (ROOT / "databases" / "cases_database.sqlite3", ["case_records", "imported_record_hashes"]),
}
BATCH_SIZE = 500


def mysql_ident(value):
    return "`" + value.replace("`", "``") + "`"


def env_config():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()
    return dict(host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]),
                user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"])


def sqlite_connection(path):
    # mode=ro guarantees the SQLite source cannot be written by this script.
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def create_table(cursor, database, table, sqlite):
    columns = sqlite.execute(f"PRAGMA table_info({mysql_ident(table)})").fetchall()
    definitions = []
    for _, name, _type, notnull, default, _pk in columns:
        if table in {"crm_records", "case_records"} and name == "Order ID":
            definition = f"{mysql_ident(name)} VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        elif table == "imported_record_hashes" and name == "record_hash":
            definition = f"{mysql_ident(name)} VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        else:
            definition = f"{mysql_ident(name)} LONGTEXT CHARACTER SET utf8mb4"
        if notnull:
            definition += " NOT NULL"
        if default is not None:
            # The only source default is CURRENT_TIMESTAMP; imported values are copied explicitly.
            definition += " DEFAULT (CURRENT_TIMESTAMP)" if default.upper() == "CURRENT_TIMESTAMP" else f" DEFAULT {default}"
        definitions.append(definition)
    if table == "imported_record_hashes":
        definitions.append("PRIMARY KEY (`record_hash`)")
    cursor.execute(f"CREATE TABLE {mysql_ident(database)}.{mysql_ident(table)} (" + ", ".join(definitions) + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    if table == "crm_records":
        cursor.execute(f"CREATE UNIQUE INDEX `ux_crm_order_id` ON {mysql_ident(database)}.{mysql_ident(table)} (`Order ID`)")
    elif table == "case_records":
        cursor.execute(f"CREATE INDEX `ix_cases_order_id` ON {mysql_ident(database)}.{mysql_ident(table)} (`Order ID`)")


def migrate_table(cursor, database, table, sqlite):
    columns = [row[1] for row in sqlite.execute(f"PRAGMA table_info({mysql_ident(table)})")]
    quoted = ", ".join(mysql_ident(c) for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert = f"INSERT INTO {mysql_ident(database)}.{mysql_ident(table)} ({quoted}) VALUES ({placeholders})"
    read = sqlite.execute(f"SELECT rowid, {quoted} FROM {mysql_ident(table)} ORDER BY rowid")
    batch = []
    metadata = []
    for row in read:
        batch.append(tuple(row[1:]))
        metadata.append((table, row[0]))
        if len(batch) == BATCH_SIZE:
            cursor.executemany(insert, batch)
            cursor.executemany(f"INSERT INTO {mysql_ident(database)}.`__migration_metadata` (`source_table`, `sqlite_rowid`) VALUES (%s, %s)", metadata)
            batch, metadata = [], []
    if batch:
        cursor.executemany(insert, batch)
        cursor.executemany(f"INSERT INTO {mysql_ident(database)}.`__migration_metadata` (`source_table`, `sqlite_rowid`) VALUES (%s, %s)", metadata)


def source_count(sqlite, table):
    return sqlite.execute(f"SELECT COUNT(*) FROM {mysql_ident(table)}").fetchone()[0]


def main():
    config = env_config()
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    try:
        for database in SOURCES:
            cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s", (database,))
            if cursor.fetchone()[0]:
                raise RuntimeError(f"Refusing to overwrite existing database: {database}")
        for database, (path, tables) in SOURCES.items():
            sqlite = sqlite_connection(path)
            cursor.execute(f"CREATE DATABASE {mysql_ident(database)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            cursor.execute(f"CREATE TABLE {mysql_ident(database)}.`__migration_metadata` (`source_table` VARCHAR(128) NOT NULL, `sqlite_rowid` BIGINT NOT NULL, PRIMARY KEY (`source_table`, `sqlite_rowid`)) ENGINE=InnoDB")
            for table in tables:
                create_table(cursor, database, table, sqlite)
                migrate_table(cursor, database, table, sqlite)
                cursor.execute(f"SELECT COUNT(*) FROM {mysql_ident(database)}.{mysql_ident(table)}")
                target = cursor.fetchone()[0]
                source = source_count(sqlite, table)
                if source != target:
                    raise RuntimeError(f"Row-count mismatch for {database}.{table}: source={source}, target={target}")
                # Replay verification: every immutable SQLite rowid has migration metadata;
                # therefore a second pass would insert zero records.
                cursor.execute(f"SELECT COUNT(*) FROM {mysql_ident(database)}.`__migration_metadata` WHERE `source_table`=%s", (table,))
                if cursor.fetchone()[0] != source:
                    raise RuntimeError(f"Replay metadata mismatch for {database}.{table}")
                print(f"VERIFIED {database}.{table}: rows={target}; replay_inserts=0")
            sqlite.close()
        conn.commit()
        print("MIGRATION_SUCCEEDED")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
