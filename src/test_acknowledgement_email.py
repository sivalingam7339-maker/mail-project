"""Automated tests for Phase 1 Customer Submission Acknowledgement Email."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import MagicMock, patch
import uuid

os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient

from src import portal_db
from src.portal_api import app
from src.portal_email import (
    ACKNOWLEDGEMENT_SUBJECT,
    format_acknowledgement_body,
    send_submission_acknowledgement,
    send_test_acknowledgement_email,
)
from src.portal_submissions import STORAGE_ROOT
from src.portal_schema import create_schema


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00"
    b"\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


class CustomerAcknowledgementEmailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["APP_ENV"] = "test"
        create_schema()
        cls._test_storage = Path(r"C:\Mail\storage\portal-submissions-email-test")
        cls._test_storage.mkdir(parents=True, exist_ok=True)
        import src.portal_submissions as ps

        cls._orig_storage = ps.STORAGE_ROOT
        ps.STORAGE_ROOT = cls._test_storage

    @classmethod
    def tearDownClass(cls) -> None:
        import src.portal_submissions as ps

        ps.STORAGE_ROOT = cls._orig_storage
        shutil.rmtree(cls._test_storage, ignore_errors=True)
        portal_db.close_pool()

    def test_A_and_B_valid_submission_saved_and_acknowledgement_email_triggered_after_save(self):
        """Verify (A) valid customer submission is saved to DB and (B) acknowledgement email is triggered after save."""
        idem_key = str(uuid.uuid4())
        customer_name = "Arjun Krishnan"
        customer_email = "arjun.krishnan.test@example.com"

        with patch("src.portal_email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            with TestClient(app) as client:
                response = client.post(
                    "/api/submissions",
                    data={
                        "idempotency_key": idem_key,
                        "full_name": customer_name,
                        "email": customer_email,
                        "phone": "9876543210",
                        "alternate_number": "",
                        "order_id": "DF-TEST-1001",
                        "customer_address": "12 MG Road, Bengaluru",
                        "state": "Karnataka",
                        "pincode": "560001",
                        "issue_category": "Motor / Belt Issue",
                        "subject": "Belt noise during run",
                        "description": "Unusual squeaking noise after 15 minutes of use.",
                    },
                    files=[
                        ("invoice_image", ("invoice.png", PNG_BYTES, "image/png")),
                    ],
                )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertTrue(payload["success"])
            submission_id = payload["submission_id"]

            # Verify SMTP send_message was called exactly once
            self.assertEqual(mock_smtp.send_message.call_count, 1)
            sent_msg = mock_smtp.send_message.call_args[0][0]
            self.assertEqual(sent_msg["To"], customer_email)
            self.assertEqual(sent_msg["From"], "durafit91customermail@gmail.com")
            self.assertEqual(sent_msg["Subject"], ACKNOWLEDGEMENT_SUBJECT)
            body_text = sent_msg.get_content().strip()
            expected_body = format_acknowledgement_body(customer_name).strip()
            self.assertEqual(body_text, expected_body)
            self.assertIn("Dear Arjun Krishnan,", body_text)
            self.assertIn("Regards,\nDurafit91 Customer Support Team", body_text)

        # Verify database record in portal_submissions, portal_email_outbox, and portal_submission_events
        sub_bytes = uuid.UUID(submission_id).bytes
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT full_name, email_address, submission_status FROM `durafit_portal_test`.`portal_submissions` WHERE submission_id = %s",
                (sub_bytes,),
            )
            sub_row = cur.fetchone()
            self.assertIsNotNone(sub_row)
            self.assertEqual(sub_row["full_name"], customer_name)
            self.assertEqual(sub_row["email_address"], customer_email)
            self.assertEqual(sub_row["submission_status"], "pending_verification")

            cur.execute(
                "SELECT message_type, delivery_status, sent_at, provider_message_id FROM `durafit_portal_test`.`portal_email_outbox` WHERE submission_id = %s",
                (sub_bytes,),
            )
            outbox_row = cur.fetchone()
            self.assertIsNotNone(outbox_row)
            self.assertEqual(outbox_row["message_type"], "customer_confirmation")
            self.assertEqual(outbox_row["delivery_status"], "sent")
            self.assertIsNotNone(outbox_row["sent_at"])
            self.assertTrue(outbox_row["provider_message_id"])

            cur.execute(
                "SELECT event_type FROM `durafit_portal_test`.`portal_submission_events` WHERE submission_id = %s ORDER BY event_id ASC",
                (sub_bytes,),
            )
            events = [row["event_type"] for row in cur.fetchall()]
            self.assertIn("submission_created", events)
            self.assertIn("acknowledgement_email_sent", events)
            # Ensure submission_created happened before acknowledgement_email_sent
            self.assertLess(
                events.index("submission_created"),
                events.index("acknowledgement_email_sent"),
            )

    def test_C_failed_database_submission_does_not_trigger_email(self):
        """Verify (C) a failed database submission does NOT trigger an acknowledgement email."""
        idem_key = str(uuid.uuid4())

        with patch("src.portal_email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            with TestClient(app) as client:
                # Missing required invoice extension / unsupported content_type causes 422 before commit
                response = client.post(
                    "/api/submissions",
                    data={
                        "idempotency_key": idem_key,
                        "full_name": "Failed Submission Customer",
                        "email": "failed.customer@example.com",
                        "phone": "9876543210",
                        "order_id": "DF-TEST-1001",
                        "customer_address": "99 Failure Lane",
                        "pincode": "560001",
                        "issue_category": "Installation",
                        "description": "Should fail before DB save.",
                    },
                    files=[
                        ("invoice_image", ("invalid_file.txt", b"not-an-image", "text/plain")),
                    ],
                )

            self.assertEqual(response.status_code, 422)
            mock_smtp.send_message.assert_not_called()

    def test_D_replayed_or_repeated_submission_does_not_send_duplicate_acknowledgement_email(self):
        """Verify (D) repeating the same submission / idempotency key does NOT send a duplicate email."""
        idem_key = str(uuid.uuid4())
        customer_email = "idempotent.customer@example.com"

        with patch("src.portal_email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            with TestClient(app) as client:
                form_data = {
                    "idempotency_key": idem_key,
                    "full_name": "Meera Nair",
                    "customer_email": customer_email,
                    "phone": "9123456789",
                    "order_id": "DF-TEST-1002",
                    "customer_address": "45 Marine Drive, Kochi",
                    "pincode": "682001",
                    "issue_category": "Console Display",
                    "description": "Display flickers intermittently.",
                }
                first_resp = client.post(
                    "/api/submissions",
                    data=form_data,
                    files=[("invoice_image", ("invoice.png", PNG_BYTES, "image/png"))],
                )
                self.assertEqual(first_resp.status_code, 200)
                first_sub_id = first_resp.json()["submission_id"]
                self.assertEqual(mock_smtp.send_message.call_count, 1)

                # Replay exact same idempotency_key via POST /api/submissions
                second_resp = client.post(
                    "/api/submissions",
                    data=form_data,
                    files=[("invoice_image", ("invoice.png", PNG_BYTES, "image/png"))],
                )
                self.assertEqual(second_resp.status_code, 200)
                self.assertEqual(second_resp.json()["submission_id"], first_sub_id)
                # Still only 1 email sent
                self.assertEqual(mock_smtp.send_message.call_count, 1)

                # Also directly invoke send_submission_acknowledgement again for the same submission_id
                repeat_result = send_submission_acknowledgement(
                    submission_id=first_sub_id,
                    customer_name="Meera Nair",
                    recipient_email=customer_email,
                )
                self.assertFalse(repeat_result["sent"])
                self.assertTrue(repeat_result["skipped"])
                self.assertEqual(repeat_result["reason"], "already_sent")
                self.assertEqual(mock_smtp.send_message.call_count, 1)

    def test_E_manual_test_acknowledgement_helper(self):
        """Verify the manual development/test helper sends exactly one formatted acknowledgement email."""
        with patch("src.portal_email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

            result = send_test_acknowledgement_email(
                recipient_email="qa.recipient@example.com",
                customer_name="QA Tester",
            )
            self.assertTrue(result["sent"])
            self.assertEqual(result["from_email"], "durafit91customermail@gmail.com")
            self.assertEqual(result["recipient_email"], "qa.recipient@example.com")
            self.assertEqual(result["subject"], ACKNOWLEDGEMENT_SUBJECT)
            self.assertEqual(mock_smtp.send_message.call_count, 1)


if __name__ == "__main__":
    unittest.main()
