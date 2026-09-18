"""Read-only integration tests for the customer portal order lookup API."""

import unittest
from urllib.parse import quote

from fastapi.testclient import TestClient

from src import portal_db
from src.portal_api import app


class PortalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Obtain one real, non-null CRM Order ID without printing it or changing data.
        with portal_db.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT `Order ID` FROM `durafit_crm`.`crm_records` WHERE `Order ID` IS NOT NULL LIMIT 1")
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            raise RuntimeError("No CRM Order ID is available for the read-only integration test.")
        cls.existing_order_id = row[0]

    @classmethod
    def tearDownClass(cls):
        portal_db.close_pool()

    def test_valid_existing_order_id_returns_only_approved_fields(self):
        with TestClient(app) as client:
            response = client.get(f"/api/orders/{quote(self.existing_order_id, safe='')}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {
            "order_id", "cx_name", "account_name", "product_type", "product_name", "order_date",
            "place_of_supply", "purchased_product", "sku_new", "name", "mobile_number", "customer_email",
        })
        self.assertEqual(response.json()["order_id"], self.existing_order_id)

    def test_specified_order_returns_expanded_crm_fields(self):
        with TestClient(app) as client:
            response = client.get("/api/orders/OD337965765300998100")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["order_id"], "OD337965765300998100")
        for field in ("cx_name", "account_name", "product_type", "product_name", "order_date", "place_of_supply"):
            self.assertIn(field, body)
        self.assertNotIn("sales_order_owner", body)

    def test_invalid_order_id_returns_not_found(self):
        with TestClient(app) as client:
            response = client.get("/api/orders/TEST-INVALID-999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Order ID not found"})


if __name__ == "__main__":
    unittest.main()
