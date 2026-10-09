"""Customer submission acknowledgement email service (Phase 1)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
from unittest.mock import MagicMock
import uuid

from dotenv import dotenv_values
import mysql.connector

from src.portal_db import mysql_options, portal_database_name


ACKNOWLEDGEMENT_SUBJECT = "Thank You for Contacting Durafit91"
DEFAULT_SENDER_EMAIL = "durafit91customermail@gmail.com"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_test_environment() -> bool:
    return (os.getenv("APP_ENV") or "").strip().lower() == "test"


def _env_file_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    if is_test_environment():
        test_path = root / ".env.test"
        if test_path.exists():
            return test_path
    return root / ".env"


def load_smtp_config() -> dict[str, str | int]:
    """Load SMTP settings from environment / .env.test without exposing secrets."""
    values = dotenv_values(_env_file_path())

    def _pick(key: str, default: str = "") -> str:
        val = os.getenv(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
        file_val = values.get(key)
        if file_val is not None and str(file_val).strip() != "":
            return str(file_val).strip()
        return default

    host = _pick("SMTP_HOST", "smtp.gmail.com")
    port_raw = _pick("SMTP_PORT", "587")
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = _pick("SMTP_USER", DEFAULT_SENDER_EMAIL)
    password = _pick("SMTP_PASSWORD", "")
    sender = _pick("SMTP_FROM", user or DEFAULT_SENDER_EMAIL)
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": sender,
    }


def format_acknowledgement_body(customer_name: str | None) -> str:
    """Return the exact required plain-text acknowledgement email body."""
    clean_name = (customer_name or "").strip() or "Customer"
    return (
        f"Dear {clean_name},\n\n"
        "Thank you so much for contacting Durafit91 and submitting the customer\n"
        "support form.\n\n"
        "We have successfully received your request. Our team will review your\n"
        "concern and guide you shortly.\n\n"
        "If you have any additional information, please feel free to reply to this\n"
        "email.\n\n"
        "Thank you for choosing Durafit91.\n\n"
        "Regards,\n"
        "Durafit91 Customer Support Team"
    )


def build_acknowledgement_email(
    recipient_email: str,
    customer_name: str | None,
    sender_email: str | None = None,
) -> EmailMessage:
    """Construct the RFC-compliant EmailMessage for customer acknowledgement."""
    config = load_smtp_config()
    from_addr = (sender_email or str(config["from_email"]) or DEFAULT_SENDER_EMAIL).strip()
    to_addr = (recipient_email or "").strip()
    if not to_addr or "@" not in to_addr:
        raise ValueError("A valid recipient email address is required")

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Reply-To"] = from_addr
    msg["Subject"] = ACKNOWLEDGEMENT_SUBJECT
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@durafit91.local>"
    msg.set_content(format_acknowledgement_body(customer_name))
    return msg


def _is_smtp_mocked() -> bool:
    return isinstance(smtplib.SMTP, MagicMock) or hasattr(smtplib.SMTP, "assert_called")


def send_smtp_message(
    msg: EmailMessage,
    config: dict[str, str | int] | None = None,
    allow_live_in_test: bool = False,
) -> str:
    """Send an EmailMessage over SMTP (STARTTLS on 587 or SSL on 465)."""
    cfg = config or load_smtp_config()
    host = str(cfg.get("host") or "smtp.gmail.com")
    port = int(cfg.get("port") or 587)
    user = str(cfg.get("user") or "")
    password = str(cfg.get("password") or "")
    message_id = str(msg.get("Message-ID") or f"<{uuid.uuid4().hex}@durafit91.local>")

    # During automated test runs without a mocked SMTP class, prevent accidental external
    # emails unless explicitly enabled via DURAFIT_LIVE_SMTP_TEST=1 or allow_live_in_test=True.
    if (
        is_test_environment()
        and not allow_live_in_test
        and os.getenv("DURAFIT_LIVE_SMTP_TEST") != "1"
        and not _is_smtp_mocked()
    ):
        return message_id

    if not user or not password:
        raise RuntimeError("SMTP credentials are not configured")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)

    return message_id


def send_submission_acknowledgement(
    submission_id: str,
    customer_name: str | None,
    recipient_email: str | None,
    allow_live_in_test: bool = False,
) -> dict:
    """Send an automatic acknowledgement email once for a saved submission.

    Idempotency & duplicate protection:
    - Checks `portal_email_outbox` for `submission_id` and `message_type='customer_confirmation'`.
    - If `delivery_status == 'sent'`, returns immediately without sending another email.
    - Updates `portal_email_outbox` and inserts an event into `portal_submission_events`.
    """
    clean_recipient = (recipient_email or "").strip()
    if not clean_recipient or "@" not in clean_recipient:
        return {
            "sent": False,
            "skipped": True,
            "reason": "missing_or_invalid_email",
            "submission_id": submission_id,
        }

    submission_uuid = uuid.UUID(str(submission_id))
    submission_bytes = submission_uuid.bytes

    options = mysql_options(database=portal_database_name(), pool=False)
    conn = mysql.connector.connect(**options)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT BIN_TO_UUID(outbox_id) AS outbox_id, delivery_status, provider_message_id
            FROM portal_email_outbox
            WHERE submission_id = %s AND message_type = 'customer_confirmation'
            LIMIT 1
            """,
            (submission_bytes,),
        )
        outbox_row = cur.fetchone()
        if outbox_row and outbox_row.get("delivery_status") == "sent":
            return {
                "sent": False,
                "skipped": True,
                "reason": "already_sent",
                "submission_id": submission_id,
                "provider_message_id": outbox_row.get("provider_message_id"),
            }

        if not outbox_row:
            new_outbox_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO portal_email_outbox (outbox_id, submission_id, message_type, delivery_status)
                VALUES (%s, %s, 'customer_confirmation', 'pending')
                """,
                (new_outbox_id.bytes, submission_bytes),
            )
            conn.commit()
            outbox_bytes = new_outbox_id.bytes
        else:
            outbox_bytes = uuid.UUID(outbox_row["outbox_id"]).bytes

        msg = build_acknowledgement_email(
            recipient_email=clean_recipient,
            customer_name=customer_name,
        )
        now = _now()
        try:
            provider_message_id = send_smtp_message(
                msg,
                allow_live_in_test=allow_live_in_test,
            )
            cur.execute(
                """
                UPDATE portal_email_outbox
                SET delivery_status = 'sent',
                    attempt_count = attempt_count + 1,
                    provider_message_id = %s,
                    sent_at = %s,
                    last_error = NULL
                WHERE outbox_id = %s
                """,
                (provider_message_id[:255], now, outbox_bytes),
            )
            cur.execute(
                """
                INSERT INTO portal_submission_events
                    (submission_id, case_id, event_type, event_payload, created_at)
                VALUES (%s, NULL, 'acknowledgement_email_sent', %s, %s)
                """,
                (
                    submission_bytes,
                    json.dumps(
                        {
                            "recipient_email": clean_recipient,
                            "subject": ACKNOWLEDGEMENT_SUBJECT,
                            "provider_message_id": provider_message_id,
                            "status": "sent",
                        }
                    ),
                    now,
                ),
            )
            conn.commit()
            return {
                "sent": True,
                "skipped": False,
                "submission_id": submission_id,
                "recipient_email": clean_recipient,
                "subject": ACKNOWLEDGEMENT_SUBJECT,
                "provider_message_id": provider_message_id,
            }
        except Exception as exc:
            safe_error = str(exc)[:500]
            cur.execute(
                """
                UPDATE portal_email_outbox
                SET delivery_status = 'failed',
                    attempt_count = attempt_count + 1,
                    last_error = %s
                WHERE outbox_id = %s
                """,
                (safe_error, outbox_bytes),
            )
            cur.execute(
                """
                INSERT INTO portal_submission_events
                    (submission_id, case_id, event_type, event_payload, created_at)
                VALUES (%s, NULL, 'acknowledgement_email_failed', %s, %s)
                """,
                (
                    submission_bytes,
                    json.dumps(
                        {
                            "recipient_email": clean_recipient,
                            "subject": ACKNOWLEDGEMENT_SUBJECT,
                            "status": "failed",
                            "error": safe_error,
                        }
                    ),
                    now,
                ),
            )
            conn.commit()
            return {
                "sent": False,
                "skipped": False,
                "submission_id": submission_id,
                "recipient_email": clean_recipient,
                "error": safe_error,
            }
    finally:
        conn.close()


def send_test_acknowledgement_email(
    recipient_email: str,
    customer_name: str = "Test Customer",
) -> dict:
    """Safe manual development/test helper to send ONE test acknowledgement email."""
    clean_recipient = (recipient_email or "").strip()
    msg = build_acknowledgement_email(
        recipient_email=clean_recipient,
        customer_name=customer_name,
    )
    provider_message_id = send_smtp_message(msg, allow_live_in_test=True)
    return {
        "sent": True,
        "from_email": str(msg["From"]),
        "recipient_email": clean_recipient,
        "customer_name": (customer_name or "").strip() or "Customer",
        "subject": str(msg["Subject"]),
        "provider_message_id": provider_message_id,
    }


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a single test Durafit91 customer acknowledgement email."
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient email address for the single test acknowledgement email.",
    )
    parser.add_argument(
        "--name",
        default="Test Customer",
        help="Customer name to use in the greeting (default: 'Test Customer').",
    )
    args = parser.parse_args()
    result = send_test_acknowledgement_email(
        recipient_email=args.to,
        customer_name=args.name,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
