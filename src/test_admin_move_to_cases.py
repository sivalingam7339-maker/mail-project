"""Tests for Step 3: Admin Move to Cases functionality."""

import io
import json
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
import mysql.connector

from src import portal_db
from src.portal_api import app
from src.portal_schema import create_schema
from src.admin_imports import move_submission_to_cases


class AdminMoveToCasesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_schema()
        credentials = portal_db._read_local_env()
        cls.username = credentials["ADMIN_USERNAME"]
        cls.password = credentials["ADMIN_PASSWORD"]

        # Acquire admin token
        with TestClient(app) as client:
            resp = client.post("/api/admin/login", data={"username": cls.username, "password": cls.password})
            assert resp.status_code == 200, resp.text
            cls.token = resp.json()["token"]
            cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}

        # Query Order ID from CRM that does NOT have cases in case_records
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT c.`Order ID`
                    FROM `durafit_crm`.`crm_records` c
                    WHERE c.`Order ID` REGEXP '^[[:print:]]+$'
                      AND NOT EXISTS (
                          SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID` = c.`Order ID`
                      )
                    LIMIT 1
                """)
                row = cur.fetchone()
                cls.order_id_no_cases = row[0].strip() if row else "ORDER-NO-CASE-TEST-001"

                # Query Order ID that DOES have cases
                cur.execute("""
                    SELECT `Order ID`
                    FROM `durafit_cases`.`case_records`
                    WHERE `Order ID` IS NOT NULL AND `Order ID` <> ''
                    GROUP BY `Order ID`
                    HAVING COUNT(*) >= 1
                    LIMIT 1
                """)
                row = cur.fetchone()
                cls.order_id_with_cases = row[0].strip() if row else "OD338303328366816100"
            finally:
                cur.close()

    def _create_submission(self, order_id: str, name: str = "Test Customer", phone: str = "9876543210",
                           category: str = "Product Issue (Warranty)", desc: str = "Belt slipping issue",
                           address: str = "123 Test Street", pincode: str = "560001") -> str:
        key = str(uuid.uuid4())
        files = [
            ("invoice_image", ("inv.png", io.BytesIO(b"invoice-png-data"), "image/png")),
            ("attachments", ("pic.jpg", io.BytesIO(b"pic-jpg-data"), "image/jpeg")),
        ]
        form = {
            "idempotency_key": key,
            "full_name": name,
            "phone": phone,
            "order_id": order_id,
            "customer_address": address,
            "pincode": pincode,
            "issue_category": category,
            "description": desc,
        }
        with TestClient(app) as client:
            resp = client.post("/api/submissions", data=form, files=files)
            self.assertEqual(resp.status_code, 200, resp.text)
            return resp.json()["submission_id"]

    def test_01_move_submission_with_no_existing_case(self):
        """Move a submission with no prior case: verifies case_records, portal_cases, status, event, and returned ID."""
        cust_name = f"No Case Customer {uuid.uuid4().hex[:6]}"
        sub_id = self._create_submission(
            self.order_id_no_cases,
            name=cust_name,
            phone="9123456789",
            category="Product Issue (Warranty)",
            desc="Brand new complaint for order without prior cases"
        )

        with TestClient(app) as client:
            resp = client.post(
                f"/api/admin/customer-submissions/{sub_id}/move-to-cases",
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["status"], "moved_to_cases")
            self.assertIn("case_id", data)
            case_id = data["case_id"]
            self.assertTrue(case_id.startswith("DF91-CASE-"))

        # Verify DB records
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                # 1. Exactly one case_records row for this Order ID with Status = 'Created'
                cur.execute("SELECT * FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s AND `Customer` = %s", (self.order_id_no_cases, cust_name))
                cases = cur.fetchall()
                self.assertEqual(len(cases), 1)
                self.assertEqual(cases[0]["Status"], "Created")

                # 2. Exactly one portal_cases row
                cur.execute("SELECT * FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                portal_case = cur.fetchone()
                self.assertIsNotNone(portal_case)
                self.assertEqual(portal_case["case_id"], case_id)
                self.assertEqual(portal_case["case_status"], "created")

                # 3. Submission status updated to moved_to_cases
                cur.execute("SELECT submission_status FROM `durafit_portal`.`portal_submissions` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                sub_row = cur.fetchone()
                self.assertEqual(sub_row["submission_status"], "moved_to_cases")

                # 4. Audit event created
                cur.execute("""
                    SELECT * FROM `durafit_portal`.`portal_submission_events`
                    WHERE submission_id = UUID_TO_BIN(%s) AND event_type = 'moved_to_cases'
                """, (sub_id,))
                event = cur.fetchone()
                self.assertIsNotNone(event)
                self.assertEqual(event["case_id"], case_id)
            finally:
                cur.close()

    def test_02_move_submission_whose_order_id_already_has_cases(self):
        """Move a submission whose Order ID already has cases: preserves old records, adds exactly one new case row."""
        cust_name = f"Repeat Case Customer {uuid.uuid4().hex[:6]}"
        # 1. Inspect existing cases for this Order ID
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("SELECT * FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s", (self.order_id_with_cases,))
                prior_cases = cur.fetchall()
                prior_count = len(prior_cases)
                self.assertGreaterEqual(prior_count, 1)
            finally:
                cur.close()

        # 2. Create fresh submission for that same Order ID
        sub_id = self._create_submission(
            self.order_id_with_cases,
            name=cust_name,
            phone="9876500000",
            category="Free Installation",
            desc="Followup service installation request"
        )

        # 3. Move to cases
        with TestClient(app) as client:
            resp = client.post(
                f"/api/admin/customer-submissions/{sub_id}/move-to-cases",
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["status"], "moved_to_cases")
            new_case_id = data["case_id"]

        # 4. Verify DB: exactly 1 new case row added, existing rows remain unchanged
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("SELECT * FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s", (self.order_id_with_cases,))
                after_cases = cur.fetchall()
                self.assertEqual(len(after_cases), prior_count + 1)

                # Prior cases are intact
                matching_new = [c for c in after_cases if c["Customer"] == cust_name]
                self.assertEqual(len(matching_new), 1)
                self.assertEqual(matching_new[0]["Status"], "Created")
                self.assertEqual(matching_new[0]["Case Type"], "Free Installation")

                # Verify submission moved
                cur.execute("SELECT submission_status FROM `durafit_portal`.`portal_submissions` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                self.assertEqual(cur.fetchone()["submission_status"], "moved_to_cases")

                # Verify portal_cases record
                cur.execute("SELECT case_id FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                self.assertEqual(cur.fetchone()["case_id"], new_case_id)
            finally:
                cur.close()

    def test_03_idempotency_moving_twice_returns_same_case_without_duplicate(self):
        """Calling Move to Cases multiple times must return the same case ID and create NO duplicate rows."""
        cust_name = f"Idempotent Customer {uuid.uuid4().hex[:6]}"
        sub_id = self._create_submission(
            self.order_id_no_cases,
            name=cust_name,
            phone="9111222333",
            category="Product Issue (Warranty)",
            desc="Testing idempotency"
        )

        with TestClient(app) as client:
            # First call
            resp1 = client.post(
                f"/api/admin/customer-submissions/{sub_id}/move-to-cases",
                headers=self.auth_headers,
            )
            self.assertEqual(resp1.status_code, 200)
            data1 = resp1.json()
            case_id_1 = data1["case_id"]

            # Snapshot counts
            with portal_db.connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT COUNT(*) FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s", (self.order_id_no_cases,))
                    cases_count_after_first = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                    portal_cases_count_after_first = cur.fetchone()[0]
                    self.assertEqual(portal_cases_count_after_first, 1)
                finally:
                    cur.close()

            # Second call (retry / duplicate click)
            resp2 = client.post(
                f"/api/admin/customer-submissions/{sub_id}/move-to-cases",
                headers=self.auth_headers,
            )
            self.assertEqual(resp2.status_code, 200)
            data2 = resp2.json()
            self.assertTrue(data2["success"])
            self.assertEqual(data2["case_id"], case_id_1)
            self.assertTrue(data2.get("already_moved", False))

            # Verify NO new rows added to either table
            with portal_db.connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT COUNT(*) FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s", (self.order_id_no_cases,))
                    cases_count_after_second = cur.fetchone()[0]
                    self.assertEqual(cases_count_after_second, cases_count_after_first)

                    cur.execute("SELECT COUNT(*) FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                    portal_cases_count_after_second = cur.fetchone()[0]
                    self.assertEqual(portal_cases_count_after_second, 1)
                finally:
                    cur.close()

    def test_04_failure_rollback_leaves_no_partial_records(self):
        """If an error occurs mid-transaction, rolls back completely without leaving partial records."""
        sub_id = self._create_submission(
            "FAIL-ROLLBACK-ORDER-999",
            name="Rollback Customer",
            phone="9000000000",
            category="Product Issue (Warranty)",
            desc="Testing rollback upon failure"
        )

        # Count records before
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM `durafit_cases`.`case_records` WHERE `Order ID` = 'FAIL-ROLLBACK-ORDER-999'")
                case_count_before = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                portal_count_before = cur.fetchone()[0]
                self.assertEqual(portal_count_before, 0)
            finally:
                cur.close()

        # Simulate failure in the middle of move_submission_to_cases by mocking portal_cases insert
        real_execute = mysql.connector.cursor.MySQLCursor.execute

        def failing_execute(cursor_self, operation, params=None, multi=False):
            if "INSERT INTO `durafit_portal`.`portal_cases`" in str(operation):
                raise mysql.connector.Error("Simulated database failure during portal_cases insert")
            return real_execute(cursor_self, operation, params, multi)

        with patch.object(mysql.connector.cursor.MySQLCursor, "execute", new=failing_execute):
            with self.assertRaises(mysql.connector.Error):
                move_submission_to_cases(sub_id, admin_user="admin")

        # Verify atomic rollback: no case_records inserted, no portal_cases inserted, submission remains pending_verification
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("SELECT COUNT(*) as cnt FROM `durafit_cases`.`case_records` WHERE `Order ID` = 'FAIL-ROLLBACK-ORDER-999'")
                case_count_after = cur.fetchone()["cnt"]
                self.assertEqual(case_count_after, case_count_before)

                cur.execute("SELECT COUNT(*) as cnt FROM `durafit_portal`.`portal_cases` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                portal_count_after = cur.fetchone()["cnt"]
                self.assertEqual(portal_count_after, 0)

                cur.execute("SELECT submission_status FROM `durafit_portal`.`portal_submissions` WHERE submission_id = UUID_TO_BIN(%s)", (sub_id,))
                sub_status = cur.fetchone()["submission_status"]
                self.assertEqual(sub_status, "pending_verification")
            finally:
                cur.close()

    def test_05_verify_created_case_fields_mapping(self):
        """Verify the created case contains the expected mapped customer, product, issue category, status and date fields."""
        # Query order with known CRM fields
        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("""
                    SELECT `Order ID`, `SKU new`, `Product Name`, `Purchased Product`, `Sales Order Owner`
                    FROM `durafit_crm`.`crm_records`
                    WHERE `Order ID` REGEXP '^[[:print:]]+$'
                      AND `Product Name` IS NOT NULL
                      AND `SKU new` IS NOT NULL
                    LIMIT 1
                """)
                crm_record = cur.fetchone()
                order_id = crm_record["Order ID"].strip() if crm_record else self.order_id_no_cases
            finally:
                cur.close()

        cust_name = "Detailed Customer " + uuid.uuid4().hex[:6]
        phone = "9876543210"
        address = "77 Innovation Park, Sector 4"
        pincode = "560100"
        category = "Product Issue (Warranty)"
        description = "Console screen flickering when running at speed 10."

        sub_id = self._create_submission(
            order_id,
            name=cust_name,
            phone=phone,
            category=category,
            desc=description,
            address=address,
            pincode=pincode,
        )

        with TestClient(app) as client:
            resp = client.post(
                f"/api/admin/customer-submissions/{sub_id}/move-to-cases",
                headers=self.auth_headers,
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            case_id = data["case_id"]

        with portal_db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("SELECT * FROM `durafit_cases`.`case_records` WHERE `Order ID` = %s AND `Customer` = %s", (order_id, cust_name))
                row = cur.fetchone()
                self.assertIsNotNone(row, "New case row should exist in case_records")

                # Field assertions
                self.assertEqual(row["Order ID"], order_id)
                self.assertEqual(row["Customer"], cust_name)
                self.assertEqual(row["Mobile"], phone)
                self.assertEqual(row["Case Type"], category)
                self.assertEqual(row["Status"], "Created")
                self.assertIsNone(row["Spares"])
                self.assertIn(description, row["Comment"])
                self.assertIn(address, row["Comment"])
                self.assertIn(pincode, row["Comment"])
                self.assertEqual(row["Created By"], self.username)
                today_formatted = datetime.now().strftime("%d-%b-%Y")
                self.assertEqual(row["Created Date"], today_formatted)
                self.assertIsNone(row["Closed Date"])
                self.assertIsNone(row["Amount Charged"])
                self.assertIsNone(row["Amount to Tech"])
                self.assertIsNone(row["Visit Status"])
                self.assertIsNone(row["Technician Resolution"])

                if crm_record:
                    if crm_record.get("SKU new"):
                        self.assertEqual(row["SKU"], crm_record["SKU new"])
                    expected_product = crm_record.get("Purchased Product") or crm_record.get("Product Name")
                    if expected_product:
                        self.assertEqual(row["Product"], expected_product)
                    if crm_record.get("Sales Order Owner"):
                        self.assertEqual(row["SO Owner"], crm_record["Sales Order Owner"])
            finally:
                cur.close()


if __name__ == "__main__":
    unittest.main()
