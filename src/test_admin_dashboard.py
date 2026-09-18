"""Controlled tests for protected admin APIs and incremental MySQL imports."""

import io
import uuid
import unittest

from fastapi.testclient import TestClient
from openpyxl import Workbook

from src.portal_api import app
from src.portal_db import _read_local_env
from src.portal_schema import create_schema


def workbook_bytes(headers, rows, sheet_name="Sheet", extra_sheet=False):
    book = Workbook(); sheet = book.active; sheet.title=sheet_name; sheet.append(headers)
    for row in rows: sheet.append(row)
    if extra_sheet: book.create_sheet("Ignored Notes").append(["not CRM data"])
    stream = io.BytesIO(); book.save(stream); return stream.getvalue()


class AdminDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_schema(); values = _read_local_env(); cls.username=values['ADMIN_USERNAME']; cls.password=values['ADMIN_PASSWORD']
        with TestClient(app) as client:
            response=client.post('/api/admin/login',data={'username':cls.username,'password':cls.password})
        cls.token=response.json()['token']
        cls.headers={'Authorization':f'Bearer {cls.token}'}

    def post_import(self, kind, content):
        with TestClient(app) as client:
            return client.post(f'/api/admin/import/{kind}',headers=self.headers,files={'file':(f'test-{kind}.xlsx',content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})

    def test_login_and_protection(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/admin/stats').status_code,401)
            self.assertEqual(client.post('/api/admin/login',data={'username':'invalid','password':'invalid'}).status_code,401)
            self.assertEqual(client.get('/api/admin/stats',headers=self.headers).status_code,200)
            self.assertEqual(client.post('/api/admin/logout',headers=self.headers).status_code,200)
            self.assertEqual(client.get('/api/admin/stats',headers=self.headers).status_code,401)
        # Refresh the test session after validating revocation.
        with TestClient(app) as client:
            self.__class__.token=client.post('/api/admin/login',data={'username':self.username,'password':self.password}).json()['token']
            self.__class__.headers={'Authorization':f'Bearer {self.token}'}

    def test_stats_are_live_aggregates(self):
        import mysql.connector
        from src.portal_db import mysql_options
        with TestClient(app) as client: response=client.get('/api/admin/stats',headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text); payload=response.json()
        conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False)); cur=conn.cursor()
        cur.execute('SELECT COUNT(*) FROM portal_submissions'); self.assertEqual(payload['customer_cases'],cur.fetchone()[0])
        cur.execute('SELECT COUNT(*) FROM `durafit_cases`.`case_records`'); self.assertEqual(payload['case_records'],cur.fetchone()[0]); self.assertEqual(payload['cases_records'],payload['case_records'])
        cur.close();conn.close()
        self.assertEqual(sum(item['count'] for item in payload['case_status_breakdown']),payload['cases_records'])
        self.assertEqual(payload['customer_case_breakdown']['order_id_exists'] + payload['customer_case_breakdown']['need_to_create_case'],payload['customer_cases'])
        self.assertEqual(payload['crm_status_breakdown']['order_id_exists'] + payload['crm_status_breakdown']['order_id_not_found'],payload['customer_cases'])
        self.assertIsInstance(payload['case_status_breakdown'], list)
        self.assertIn('order_id_exists', payload['customer_case_breakdown'])
        self.assertIn('order_id_not_found', payload['crm_status_breakdown'])

    def test_crm_incremental_import(self):
        import mysql.connector
        from src.portal_db import mysql_options
        conn=mysql.connector.connect(**mysql_options(database='durafit_crm',pool=False)); cur=conn.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='durafit_crm' AND TABLE_NAME='crm_records' ORDER BY ORDINAL_POSITION"); headers=[r[0] for r in cur.fetchall()]
        cur.execute("SELECT `Order ID` FROM crm_records WHERE `Order ID` IS NOT NULL LIMIT 1"); existing=cur.fetchone()[0]; cur.close();conn.close()
        new_id='ADMIN-CRM-'+uuid.uuid4().hex[:16].upper(); row=[None]*len(headers); row[headers.index('Order ID')]=new_id; row[headers.index('Name')]='Admin Test'; row[headers.index('Product Name')]='Test Product'
        old=[None]*len(headers); old[headers.index('Order ID')]=existing
        content=workbook_bytes(headers,[row,old],sheet_name="Sales Order",extra_sheet=True); first=self.post_import('crm',content).json(); second=self.post_import('crm',content).json()
        self.assertEqual((first['inserted_rows'],first['skipped_rows']),(1,1)); self.assertEqual((second['inserted_rows'],second['skipped_rows']),(0,2))

    def test_crm_dry_run_uses_sales_order_in_multisheet_workbook(self):
        import mysql.connector
        from src.portal_db import mysql_options
        conn=mysql.connector.connect(**mysql_options(database='durafit_crm',pool=False)); cur=conn.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='durafit_crm' AND TABLE_NAME='crm_records' ORDER BY ORDINAL_POSITION"); headers=[r[0] for r in cur.fetchall()]
        row=[None]*len(headers); row[headers.index('Order ID')]='DRY-RUN-'+uuid.uuid4().hex[:16].upper(); row[headers.index('Name')]='Dry Run Only';cur.close();conn.close()
        content=workbook_bytes(headers,[row],sheet_name='Sales Order',extra_sheet=True)
        with TestClient(app) as client:
            response=client.post('/api/admin/import/crm/dry-run',headers=self.headers,files={'file':('crm.xlsx',content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        self.assertEqual(response.status_code,200,response.text); self.assertEqual(response.json()['source_sheet'],'Sales Order'); self.assertEqual(response.json()['new_records'],1)

    def test_cases_hash_import_allows_same_order_different_rows(self):
        import mysql.connector
        from src.portal_db import mysql_options
        conn=mysql.connector.connect(**mysql_options(database='durafit_cases',pool=False)); cur=conn.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='durafit_cases' AND TABLE_NAME='case_records' ORDER BY ORDINAL_POSITION"); headers=[r[0] for r in cur.fetchall()];cur.close();conn.close()
        order='ADMIN-CASE-'+uuid.uuid4().hex[:16].upper(); first=[None]*len(headers); second=[None]*len(headers)
        for row, comment in ((first,'first controlled case'),(second,'second controlled case')): row[headers.index('Order ID')]=order; row[headers.index('Comment')]=comment
        content=workbook_bytes(headers,[first,second]); summary=self.post_import('cases',content).json(); repeat=self.post_import('cases',content).json()
        self.assertEqual(summary['inserted_rows'],2); self.assertEqual(repeat['skipped_rows'],2)

    def test_history_exists(self):
        with TestClient(app) as client: response=client.get('/api/admin/import/history',headers=self.headers)
        self.assertEqual(response.status_code,200); self.assertTrue(response.json())

    def test_customer_cases_are_protected_searchable_and_have_dynamic_statuses(self):
        """Portal submissions are listed from durafit_portal with status values in each row."""
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/admin/customer-cases').status_code, 401)
            response=client.get('/api/admin/customer-cases',headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            payload=response.json(); self.assertGreater(payload['total'], 0)
            row=payload['items'][0]
            self.assertIn(row['crm_status'], {'Order ID Exists','Order ID Not Found'})
            self.assertTrue(row['case_statuses'])
            by_order=client.get('/api/admin/customer-cases',params={'search':row['order_id']},headers=self.headers)
            self.assertEqual(by_order.status_code,200); self.assertTrue(any(x['submission_id']==row['submission_id'] for x in by_order.json()['items']))
            detail=client.get('/api/admin/customer-cases/'+row['submission_id'],headers=self.headers)
            self.assertEqual(detail.status_code,200); self.assertEqual(detail.json()['order_id'],row['order_id'])
            attachments=detail.json()['attachments']
            if attachments:
                path=f"/api/admin/customer-cases/{row['submission_id']}/attachments/{attachments[0]['attachment_id']}"
                self.assertEqual(client.get(path).status_code,401)
                self.assertEqual(client.get(path,headers=self.headers).status_code,200)


if __name__ == '__main__': unittest.main()
