"""One-time streamed migration of local durafit_crm to an empty Aiven target.

The destination session receives sql_require_primary_key=OFF before any dump
input is written.  Nothing in this script changes the local MySQL instance.
"""

from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import mysql.connector


ROOT = Path(__file__).resolve().parent
MYSQL_BIN = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe")
MYSQLDUMP_BIN = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe")
DATABASE = "durafit_crm"
SESSION_MARKER = "__DURAFIT_SESSION_PRIMARY_KEY_OFF__"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def local_config() -> dict[str, object]:
    values = read_env(ROOT / ".env")
    return {"host": values["MYSQL_HOST"], "port": int(values["MYSQL_PORT"]), "user": values["MYSQL_USER"], "password": values["MYSQL_PASSWORD"]}


def aiven_config() -> dict[str, object]:
    values = read_env(ROOT / ".env.aiven")
    return {"host": values["AIVEN_MYSQL_HOST"], "port": int(values["AIVEN_MYSQL_PORT"]), "user": values["AIVEN_MYSQL_USER"], "password": values["AIVEN_MYSQL_PASSWORD"]}


def target_connection(config: dict[str, object], database: str | None = None):
    options = {**config, "ssl_disabled": False, "connection_timeout": 15}
    if database:
        options["database"] = database
    return mysql.connector.connect(**options)


def scalar(cursor, statement: str, parameters: tuple[object, ...] = ()) -> int:
    cursor.execute(statement, parameters)
    return int(cursor.fetchone()[0])


def assert_target_empty(config: dict[str, object]) -> None:
    conn = target_connection(config)
    cursor = conn.cursor()
    try:
        schemas = scalar(cursor, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s", (DATABASE,))
        if schemas != 1:
            raise RuntimeError(f"Aiven target database {DATABASE!r} does not exist.")
        checks = {
            "tables": "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s",
            "routines": "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema=%s",
            "events": "SELECT COUNT(*) FROM information_schema.events WHERE event_schema=%s",
            "triggers": "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=%s",
        }
        found = {name: scalar(cursor, statement, (DATABASE,)) for name, statement in checks.items()}
        if any(found.values()):
            detail = ", ".join(f"{name}={count}" for name, count in found.items())
            raise RuntimeError(f"Aiven {DATABASE} is not empty ({detail}). Refusing migration.")
        print("AIVEN_EMPTY_CHECK=PASS tables=0 routines=0 events=0 triggers=0")
    finally:
        cursor.close()
        conn.close()


def reader(stream, lines: queue.Queue[str]) -> None:
    for line in iter(stream.readline, ""):
        lines.put(line)
    stream.close()


def collect(lines: queue.Queue[str]) -> list[str]:
    result: list[str] = []
    while True:
        try:
            result.append(lines.get_nowait())
        except queue.Empty:
            return result


def command_env(password: object) -> dict[str, str]:
    env = os.environ.copy()
    env["MYSQL_PWD"] = str(password)
    return env


def migrate(local: dict[str, object], aiven: dict[str, object]) -> None:
    mysql_command = [str(MYSQL_BIN), "--host", str(aiven["host"]), "--port", str(aiven["port"]), "--user", str(aiven["user"]), "--ssl-mode=REQUIRED", "--batch", "--skip-column-names", DATABASE]
    destination = subprocess.Popen(mysql_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=command_env(aiven["password"]))
    assert destination.stdin and destination.stdout and destination.stderr
    output, errors = queue.Queue(), queue.Queue()
    threading.Thread(target=reader, args=(destination.stdout, output), daemon=True).start()
    threading.Thread(target=reader, args=(destination.stderr, errors), daemon=True).start()

    destination.stdin.write(f"SET SESSION sql_require_primary_key = OFF; SELECT '{SESSION_MARKER}', @@SESSION.sql_require_primary_key;\n")
    destination.stdin.flush()
    deadline = time.monotonic() + 20
    stdout, stderr = [], []
    confirmed = False
    while time.monotonic() < deadline and destination.poll() is None:
        stdout.extend(collect(output)); stderr.extend(collect(errors))
        if stderr:
            destination.stdin.close(); destination.wait(timeout=10)
            stderr.extend(collect(errors))
            raise RuntimeError("Aiven session SET command was rejected. mysql stderr:\n" + "".join(stderr).strip())
        if any(line.strip() == f"{SESSION_MARKER}\t0" for line in stdout):
            confirmed = True
            break
        time.sleep(0.05)
    if not confirmed:
        destination.stdin.close(); destination.wait(timeout=10)
        stderr.extend(collect(errors)); stdout.extend(collect(output))
        raise RuntimeError("Aiven session sql_require_primary_key was not confirmed OFF. mysql stderr:\n" + "".join(stderr).strip())
    print("AIVEN_SESSION_SQL_REQUIRE_PRIMARY_KEY=OFF")

    dump_command = [str(MYSQLDUMP_BIN), "--host", str(local["host"]), "--port", str(local["port"]), "--user", str(local["user"]), "--single-transaction", "--routines", "--triggers", "--events", "--hex-blob", DATABASE]
    source = subprocess.Popen(dump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=command_env(local["password"]))
    assert source.stdout and source.stderr
    try:
        while chunk := source.stdout.read(1024 * 1024):
            destination.stdin.buffer.write(chunk)
        source.stdout.close()
        source_stderr = source.stderr.read().decode("utf-8", "replace")
        source_code = source.wait()
        destination.stdin.close()
        destination_code = destination.wait()
        stderr.extend(collect(errors)); stdout.extend(collect(output))
    finally:
        if source.poll() is None:
            source.kill()
        if destination.poll() is None:
            destination.kill()
    print(f"MYSQLDUMP_EXIT_CODE={source_code}")
    print(f"AIVEN_MYSQL_EXIT_CODE={destination_code}")
    if source_stderr:
        print("MYSQLDUMP_STDERR:\n" + source_stderr.rstrip())
    if stderr:
        print("AIVEN_MYSQL_STDERR:\n" + "".join(stderr).rstrip())
    if source_code or destination_code:
        raise RuntimeError("Streamed migration failed; see captured stderr and exit codes above.")


def table_details(config: dict[str, object]) -> dict[str, dict[str, object]]:
    conn = mysql.connector.connect(**config, database=DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = sorted(row[0] for row in cursor.fetchall())
        result = {}
        for table in tables:
            cursor.execute(f"SHOW CREATE TABLE `{table.replace('`', '``')}`")
            create = cursor.fetchone()[1]
            count = scalar(cursor, f"SELECT COUNT(*) FROM `{table.replace('`', '``')}`")
            result[table] = {"rows": count, "create": create}
        return result
    finally:
        cursor.close()
        conn.close()


def verify(local: dict[str, object], aiven: dict[str, object]) -> None:
    source, target = table_details(local), table_details(aiven)
    if source.keys() != target.keys():
        raise RuntimeError(f"Table mismatch: local={sorted(source)} Aiven={sorted(target)}")
    for table in source:
        if source[table]["rows"] != target[table]["rows"]:
            raise RuntimeError(f"Row-count mismatch for {table}: local={source[table]['rows']} Aiven={target[table]['rows']}")
        if source[table]["create"] != target[table]["create"]:
            raise RuntimeError(f"Table definition mismatch for {table}.")
        print(f"TABLE_VERIFIED {table} rows={source[table]['rows']}")
    if "`crm_records`" in target["crm_records"]["create"].lower().replace(" primary key", ""):
        pass
    if "PRIMARY KEY" in target["crm_records"]["create"].upper():
        raise RuntimeError("crm_records unexpectedly has a primary key on Aiven.")
    print("CRM_RECORDS_PRIMARY_KEY=ABSENT")
    print("DURAFIT_CRM_MIGRATION_AND_VERIFICATION=SUCCESS")


def main() -> int:
    if not MYSQL_BIN.is_file() or not MYSQLDUMP_BIN.is_file():
        raise RuntimeError("Required MySQL client executables were not found.")
    local, aiven = local_config(), aiven_config()
    assert_target_empty(aiven)
    migrate(local, aiven)
    verify(local, aiven)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"MIGRATION_STOPPED: {error}", file=sys.stderr)
        raise SystemExit(1)
