"""Controlled integration tests for the application-owned portal submission flow."""

import io
import unittest
import uuid

from fastapi.testclient import TestClient

from src import portal_db
from src.portal_api import app
from src.portal_schema import create_schema


class PortalSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_schema()
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT `Order ID` FROM `durafit_crm`.`crm_records` WHERE `Order ID` REGEXP '^[[:print:]]+$' LIMIT 1")
                cls.order_id = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM `durafit_crm`.`crm_records`")
                cls.crm_row_count_before = cur.fetchone()[0]
            finally:
                cur.close()
        cls.idempotency_key = str(uuid.uuid4())

    @staticmethod
    def form_data(order_id, key):
        return {"idempotency_key": key, "full_name": "Portal Integration Test", "phone": "9000000000", "alternate_number": "",
                "order_id": order_id, "customer_address": "Controlled test address", "pincode": "600001",
                "issue_category": "Product issue", "description": "Controlled integration test only."}

    def test_01_valid_submission_with_invoice_and_multiple_images(self):
        files = [("invoice_image", ("invoice.png", io.BytesIO(b"invoice-test"), "image/png")),
                 ("attachments", ("image-one.jpg", io.BytesIO(b"image-one"), "image/jpeg")),
                 ("attachments", ("image-two.png", io.BytesIO(b"image-two"), "image/png"))]
        with TestClient(app) as client:
            response = client.post("/api/submissions", data=self.form_data(self.order_id, self.idempotency_key), files=files)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body.get("case_id"))
        self.assertEqual(body.get("status"), "pending_verification")
        self.assertNotIn("password", str(body).lower())
        self.__class__.submission_id = body["submission_id"]
        with portal_db.connection() as crm:
            cur = crm.cursor(); cur.execute("SELECT COUNT(*) FROM `durafit_crm`.`crm_records`"); self.assertEqual(cur.fetchone()[0], self.crm_row_count_before); cur.close()
        opts = portal_db.mysql_options(database="durafit_portal", pool=False)
        import mysql.connector
        conn = mysql.connector.connect(**opts); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM portal_submission_attachments WHERE submission_id=UUID_TO_BIN(%s)", (body["submission_id"],)); self.assertEqual(cur.fetchone()[0], 3)
        cur.execute("SELECT COUNT(*) FROM portal_cases WHERE submission_id=UUID_TO_BIN(%s)", (body["submission_id"],)); self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM portal_email_outbox WHERE submission_id=UUID_TO_BIN(%s) AND message_type='customer_confirmation'", (body["submission_id"],)); self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT state, subject, submission_status FROM portal_submissions WHERE submission_id=UUID_TO_BIN(%s)", (body["submission_id"],)); self.assertEqual(cur.fetchone(), (None, None, "pending_verification"))
        cur.close(); conn.close()

    def test_02_same_idempotency_key_replays_without_duplicates(self):
        files = {"invoice_image": ("retry.png", io.BytesIO(b"retry"), "image/png")}
        with TestClient(app) as client:
            response = client.post("/api/submissions", data=self.form_data(self.order_id, self.idempotency_key), files=files)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json().get("case_id"))
        self.assertEqual(response.json()["submission_id"], self.submission_id)

    def test_03_crm_missing_order_still_creates_submission_without_case(self):
        key = str(uuid.uuid4())
        missing_order = "__portal_crm_missing_" + uuid.uuid4().hex
        files = {"invoice_image": ("invalid.png", io.BytesIO(b"invalid"), "image/png")}
        with TestClient(app) as client:
            response = client.post("/api/submissions", data=self.form_data(missing_order, key), files=files)
        self.assertEqual(response.status_code, 200, response.text)
        opts = portal_db.mysql_options(database="durafit_portal", pool=False)
        import mysql.connector
        conn = mysql.connector.connect(**opts); cur = conn.cursor()
        submission_id=response.json()["submission_id"]
        cur.execute("SELECT order_id,crm_order_id,crm_product_name,submission_status FROM portal_submissions WHERE idempotency_key=%s", (key,)); self.assertEqual(cur.fetchone(), (missing_order,None,None,"pending_verification"))
        cur.execute("SELECT COUNT(*) FROM portal_cases WHERE submission_id=UUID_TO_BIN(%s)", (submission_id,)); self.assertEqual(cur.fetchone()[0], 0)
        cur.close(); conn.close()
        credentials=portal_db._read_local_env()
        with TestClient(app) as client:
            token=client.post('/api/admin/login',data={'username':credentials['ADMIN_USERNAME'],'password':credentials['ADMIN_PASSWORD']}).json()['token']
            rows=client.get('/api/admin/customer-cases',params={'search':missing_order},headers={'Authorization':f'Bearer {token}'}).json()['items']
        self.assertEqual(rows[0]['crm_status'], 'Order ID Not Found')
        self.assertEqual(rows[0]['case_statuses'], ['Need to Create Case'])

    def test_04_submission_accepted_when_order_id_already_exists_in_durafit_cases(self):
        with portal_db.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT `Order ID` FROM `durafit_cases`.`case_records` WHERE `Order ID` IS NOT NULL AND `Order ID` <> '' LIMIT 1")
                row = cur.fetchone()
                existing_case_order_id = row[0] if row else "OD338303328366816100"
            finally:
                cur.close()

        key = str(uuid.uuid4())
        files = {"invoice_image": ("invoice_case_exists.png", io.BytesIO(b"invoice_case_exists"), "image/png")}
        with TestClient(app) as client:
            response = client.post("/api/submissions", data=self.form_data(existing_case_order_id, key), files=files)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body.get("case_id"))
        self.assertEqual(body.get("status"), "pending_verification")

        opts = portal_db.mysql_options(database="durafit_portal", pool=False)
        import mysql.connector
        conn = mysql.connector.connect(**opts); cur = conn.cursor()
        sub_id = body["submission_id"]
        cur.execute("SELECT order_id, submission_status FROM portal_submissions WHERE submission_id=UUID_TO_BIN(%s)", (sub_id,))
        self.assertEqual(cur.fetchone(), (existing_case_order_id, "pending_verification"))
        cur.execute("SELECT COUNT(*) FROM portal_cases WHERE submission_id=UUID_TO_BIN(%s)", (sub_id,))
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM portal_email_outbox WHERE submission_id=UUID_TO_BIN(%s) AND message_type='customer_confirmation'", (sub_id,))
        self.assertEqual(cur.fetchone()[0], 1)
        cur.close(); conn.close()


if __name__ == "__main__":
    unittest.main()
