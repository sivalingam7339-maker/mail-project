"""Integration tests for the Admin Customer Submissions verification module."""

import io
import unittest
import uuid

from fastapi.testclient import TestClient
import mysql.connector

from src import portal_db
from src.portal_api import app
from src.portal_schema import create_schema


class AdminCustomerSubmissionsTests(unittest.TestCase):
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

        # Find existing Order ID from CRM
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT `Order ID` FROM `durafit_crm`.`crm_records` WHERE `Order ID` REGEXP '^[[:print:]]+$' LIMIT 1")
                cls.order_id = cur.fetchone()[0].strip()
                cur.execute("SELECT `Order ID` FROM `durafit_cases`.`case_records` WHERE `Order ID` IS NOT NULL AND `Order ID` <> '' LIMIT 1")
                row = cur.fetchone()
                cls.existing_case_order_id = row[0].strip() if row and row[0] else "OD338303328366816100"
            finally:
                cur.close()

        # Create a fresh submission for verification tests
        cls.test_key = str(uuid.uuid4())
        files = [
            ("invoice_image", ("invoice_sub.png", io.BytesIO(b"invoice-data"), "image/png")),
            ("attachments", ("photo.jpg", io.BytesIO(b"photo-data"), "image/jpeg")),
        ]
        form = {
            "idempotency_key": cls.test_key,
            "full_name": "Verification Initial Name",
            "phone": "9876543210",
            "alternate_number": "9876543211",
            "order_id": cls.order_id,
            "customer_address": "123 Initial Street, Chennai",
            "pincode": "600001",
            "issue_category": "Belt Issue",
            "description": "Initial customer description for verification.",
        }
        with TestClient(app) as client:
            resp = client.post("/api/submissions", data=form, files=files)
            assert resp.status_code == 200, resp.text
            cls.submission_id = resp.json()["submission_id"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_01_list_customer_submissions(self):
        with TestClient(app) as client:
            resp = client.get("/api/admin/customer-submissions", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("case_status_options", data)
        self.assertGreater(data["total"], 0)

        # Find our created submission
        matched = [x for x in data["items"] if x["submission_id"] == self.submission_id]
        self.assertEqual(len(matched), 1)
        sub = matched[0]
        self.assertEqual(sub["order_id"], self.order_id)
        self.assertEqual(sub["full_name"], "Verification Initial Name")
        self.assertEqual(sub["phone_number"], "9876543210")
        self.assertEqual(sub["issue_category"], "Belt Issue")
        self.assertEqual(sub["crm_status"], "Order ID Exists")
        self.assertEqual(sub["submission_status_display"], "Pending Verification")

    def test_02_filter_by_submission_status(self):
        with TestClient(app) as client:
            resp = client.get(
                "/api/admin/customer-submissions?submission_status=pending_verification",
                headers=self.auth_headers,
            )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        for it in items:
            self.assertEqual(it["submission_status_display"], "Pending Verification")

    def test_03_get_customer_submission_detail(self):
        with TestClient(app) as client:
            resp = client.get(
                f"/api/admin/customer-submissions/{self.submission_id}",
                headers=self.auth_headers,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        detail = resp.json()
        self.assertEqual(detail["submission_id"], self.submission_id)
        self.assertEqual(detail["full_name"], "Verification Initial Name")
        self.assertEqual(detail["customer_address"], "123 Initial Street, Chennai")
        self.assertEqual(detail["pincode"], "600001")
        self.assertIn("crm", detail)
        self.assertEqual(detail["crm_status"], "Order ID Exists")
        self.assertIn("case_statuses", detail)
        self.assertEqual(len(detail["attachments"]), 2)

    def test_04_edit_customer_submission_fields(self):
        updated_payload = {
            "full_name": "Verified Edited Name",
            "phone_number": "9123456780",
            "alternate_number": "9123456789",
            "order_id": self.order_id,
            "customer_address": "456 Updated Boulevard, Suite 10, Chennai",
            "pincode": "600028",
            "issue_category": "Motor Not Starting",
            "detailed_description": "Admin corrected details after phone verification with customer.",
        }
        with TestClient(app) as client:
            resp = client.put(
                f"/api/admin/customer-submissions/{self.submission_id}",
                json=updated_payload,
                headers=self.auth_headers,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["full_name"], "Verified Edited Name")
        self.assertEqual(data["phone_number"], "9123456780")
        self.assertEqual(data["alternate_number"], "9123456789")
        self.assertEqual(data["customer_address"], "456 Updated Boulevard, Suite 10, Chennai")
        self.assertEqual(data["pincode"], "600028")
        self.assertEqual(data["issue_category"], "Motor Not Starting")
        self.assertEqual(data["detailed_description"], "Admin corrected details after phone verification with customer.")

        # Verify DB directly
        opts = portal_db.mysql_options(database="durafit_portal", pool=False)
        conn = mysql.connector.connect(**opts)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT full_name, phone_number, pincode FROM portal_submissions WHERE submission_id=UUID_TO_BIN(%s)", (self.submission_id,))
            row = cur.fetchone()
            self.assertEqual(row["full_name"], "Verified Edited Name")
            self.assertEqual(row["phone_number"], "9123456780")
            self.assertEqual(row["pincode"], "600028")

            # Check audit event
            cur.execute("SELECT COUNT(*) FROM portal_submission_events WHERE submission_id=UUID_TO_BIN(%s) AND event_type='submission_edited_by_admin'", (self.submission_id,))
            self.assertGreaterEqual(cur.fetchone()["COUNT(*)"], 1)
        finally:
            cur.close()
            conn.close()

    def test_05_move_to_cases_action(self):
        # Count existing rows in durafit_cases.case_records before
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM `durafit_cases`.`case_records`")
                case_count_before = cur.fetchone()[0]
            finally:
                cur.close()

        with TestClient(app) as client:
            resp = client.post(
                f"/api/admin/customer-submissions/{self.submission_id}/move-to-cases",
                headers=self.auth_headers,
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("message", data)
        self.assertIsNotNone(data.get("case_id"))

        # Verify exactly ONE new case row was created in durafit_cases.case_records
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM `durafit_cases`.`case_records`")
                case_count_after = cur.fetchone()[0]
                self.assertEqual(case_count_after, case_count_before + 1)
            finally:
                cur.close()

    def test_06_submission_with_existing_cases_is_displayed_and_not_blocked(self):
        key = str(uuid.uuid4())
        files = [("invoice_image", ("inv.png", io.BytesIO(b"data"), "image/png"))]
        form = {
            "idempotency_key": key,
            "full_name": "Existing Case Customer",
            "phone": "9998887776",
            "order_id": self.existing_case_order_id,
            "customer_address": "Test Address",
            "pincode": "560001",
            "issue_category": "Tech Visit Query",
            "description": "Customer submitting another query on order that already has cases.",
        }
        with TestClient(app) as client:
            sub_resp = client.post("/api/submissions", data=form, files=files)
            self.assertEqual(sub_resp.status_code, 200)
            sub_id = sub_resp.json()["submission_id"]

            # Query list
            list_resp = client.get(
                f"/api/admin/customer-submissions?search={self.existing_case_order_id}",
                headers=self.auth_headers,
            )
            self.assertEqual(list_resp.status_code, 200)
            items = list_resp.json()["items"]
            matched = [x for x in items if x["submission_id"] == sub_id]
            self.assertEqual(len(matched), 1)
            # Existing case status must NOT be 'Need to Create Case' because it already has cases
            self.assertNotEqual(matched[0]["case_statuses"], ["Need to Create Case"])


if __name__ == "__main__":
    unittest.main()
