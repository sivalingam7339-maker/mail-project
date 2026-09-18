"""Verify required .gitignore patterns without reading any sensitive local file."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_FILE = PROJECT_ROOT / ".gitignore"
REQUIRED_PATTERNS = {
    "credentials.json",
    "token*.json",
    "*.token.json",
    ".form_reply_replied_message_ids.json",
    ".form_processed_response_ids.json",
    ".internal_notified_response_ids.json",
    "logs/",
    "*.log",
    ".venv/",
    "venv/",
    "env/",
    "**/__pycache__/",
    "*.pyc",
    ".pytest_cache/",
}


def main() -> int:
    """Check pattern text only; no credentials, tokens, logs, or ledgers are opened."""
    patterns = {
        line.strip()
        for line in GITIGNORE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = sorted(REQUIRED_PATTERNS - patterns)
    if missing:
        raise AssertionError("Missing required .gitignore patterns: " + ", ".join(missing))
    forbidden = {"*.py", "*.md"}.intersection(patterns)
    if forbidden:
        raise AssertionError("Source or documentation files must not be broadly ignored.")
    print(".gitignore protection test passed: required sensitive/runtime patterns are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
