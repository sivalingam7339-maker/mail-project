"""Safe incremental MySQL XLSX import service for local admin use."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
import uuid

import mysql.connector
from openpyxl import load_workbook

from src.import_excel_databases import cell_text, find_order_id_column, row_hash
from src.portal_db import mysql_options


def _now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def _quote(name): return "`" + name.replace("`", "``") + "`"
BATCH_SIZE = 500


def _workbook_rows(content: bytes, source_sheet: str | None = None):
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    if source_sheet:
        if source_sheet not in book.sheetnames:
            book.close(); raise ValueError(f"{source_sheet} sheet not found in the CRM workbook.")
        sheet = book[source_sheet]
    else:
        if len(book.worksheets) != 1:
            book.close(); raise ValueError("Workbook must contain exactly one data sheet")
        sheet = book.active
    rows = sheet.iter_rows(values_only=True)
    try: headers = [cell_text(v) for v in next(rows)]
    except StopIteration: book.close(); raise ValueError("Workbook is empty")
    if any(not h or not h.strip() for h in headers) or len(set(headers)) != len(headers):
        book.close(); raise ValueError("Workbook has blank or duplicate column headings")
    return book, sheet.title, headers, rows


def _table_layout(cursor, database: str, table: str, source_headers: list[str], crm: bool):
    """Return the target-table order and validate an upload without altering schema."""
    cursor.execute("""SELECT COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION""", (database, table))
    metadata = cursor.fetchall()
    target_headers = [row[0] for row in metadata]
    if not crm:
        if source_headers != target_headers:
            raise ValueError("Workbook headers must exactly match the existing table columns")
        return target_headers
    if "Order ID" not in source_headers:
        raise ValueError("Sales Order sheet must contain an Order ID column")
    required = [name for name, nullable, default in metadata if nullable == "NO" and default is None and name not in source_headers]
    if required:
        raise ValueError("Sales Order sheet is missing required CRM columns: " + ", ".join(required))
    return target_headers


def _row_values(raw, source_headers: list[str], target_headers: list[str], crm: bool):
    if len(raw) > len(source_headers):
        return None
    source_values = [cell_text(v) for v in raw] + [None] * (len(source_headers) - len(raw))
    if not any(value is not None for value in source_values):
        return []
    if not crm:
        return source_values
    source = dict(zip(source_headers, source_values))
    return [source.get(header) for header in target_headers]


def _history(cursor, import_id, kind, filename, now):
    cursor.execute("INSERT INTO `durafit_portal`.`portal_import_history` (import_id,import_type,original_filename,started_at,status,created_at) VALUES (%s,%s,%s,%s,'running',%s)", (import_id.bytes,kind,filename[:255],now,now))


def _chunks(values, size=BATCH_SIZE):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _existing_values(cursor, table: str, column: str, values: list[str]) -> set[str]:
    """Fetch existing business keys in bounded queries without changing data."""
    found: set[str] = set()
    for chunk in _chunks(values):
        placeholders = ", ".join(["%s"] * len(chunk))
        cursor.execute(f"SELECT {_quote(column)} FROM {_quote(table)} WHERE {_quote(column)} IN ({placeholders})", chunk)
        found.update(row[0] for row in cursor.fetchall())
    return found


def _import_crm_batch(cursor, conn, insert, order_index, rows, summary):
    order_ids = list(dict.fromkeys(row[0][order_index] for row in rows if row[0][order_index] is not None))
    existing = _existing_values(cursor, "crm_records", "Order ID", order_ids) if order_ids else set()
    pending = []
    for values, digest in rows:
        order_id = values[order_index]
        if order_id is not None and order_id in existing:
            summary["skipped_rows"] += 1
            continue
        pending.append((values, digest))
        # Match the prior row-by-row behavior for duplicate Order IDs later in
        # the same workbook. NULL remains non-unique, as it was before.
        if order_id is not None:
            existing.add(order_id)
    if not pending:
        return
    try:
        conn.start_transaction()
        cursor.executemany(insert, [values for values, _ in pending])
        cursor.executemany("INSERT IGNORE INTO imported_record_hashes (record_hash) VALUES (%s)", [(digest,) for _, digest in pending])
        conn.commit()
        summary["inserted_rows"] += len(pending)
    except mysql.connector.Error:
        conn.rollback()
        # Preserve independent-row failure behavior if a batch cannot be applied.
        for values, digest in pending:
            try:
                conn.start_transaction()
                cursor.execute("SELECT 1 FROM crm_records WHERE `Order ID`=%s LIMIT 1", (values[order_index],))
                if cursor.fetchone():
                    summary["skipped_rows"] += 1
                    conn.rollback()
                    continue
                cursor.execute(insert, values)
                cursor.execute("INSERT IGNORE INTO imported_record_hashes (record_hash) VALUES (%s)", (digest,))
                conn.commit()
                summary["inserted_rows"] += 1
            except mysql.connector.Error:
                conn.rollback()
                summary["failed_rows"] += 1


def _import_cases_batch(cursor, conn, insert, rows, summary):
    digests = list(dict.fromkeys(digest for _, digest in rows))
    existing = _existing_values(cursor, "imported_record_hashes", "record_hash", digests) if digests else set()
    pending = []
    for values, digest in rows:
        if digest in existing:
            summary["skipped_rows"] += 1
            continue
        pending.append((values, digest))
        existing.add(digest)
    if not pending:
        return
    try:
        conn.start_transaction()
        cursor.executemany("INSERT INTO imported_record_hashes (record_hash) VALUES (%s)", [(digest,) for _, digest in pending])
        cursor.executemany(insert, [values for values, _ in pending])
        conn.commit()
        summary["inserted_rows"] += len(pending)
    except mysql.connector.Error:
        conn.rollback()
        # A fallback keeps a bad row from failing unrelated rows in its batch.
        for values, digest in pending:
            try:
                conn.start_transaction()
                cursor.execute("INSERT IGNORE INTO imported_record_hashes (record_hash) VALUES (%s)", (digest,))
                if cursor.rowcount == 0:
                    summary["skipped_rows"] += 1
                    conn.rollback()
                    continue
                cursor.execute(insert, values)
                conn.commit()
                summary["inserted_rows"] += 1
            except mysql.connector.Error:
                conn.rollback()
                summary["failed_rows"] += 1


def import_xlsx(kind: str, filename: str, content: bytes) -> dict:
    if kind not in {"crm", "cases"}: raise ValueError("Unknown import type")
    if not filename.lower().endswith(".xlsx"): raise ValueError("Only .xlsx files are accepted")
    database, table = ("durafit_crm", "crm_records") if kind == "crm" else ("durafit_cases", "case_records")
    import_id, now = uuid.uuid4(), _now(); summary = {"import_id": str(import_id), "import_type": kind, "total_rows": 0, "inserted_rows": 0, "skipped_rows": 0, "failed_rows": 0, "status": "completed", "error_summary": None}
    options = mysql_options(database=database, pool=False); conn = mysql.connector.connect(**options)
    book = None
    try:
        cursor = conn.cursor(); _history(cursor, import_id, kind, filename, now); conn.commit()
        book, source_sheet, source_headers, rows = _workbook_rows(content, "Sales Order" if kind == "crm" else None); find_order_id_column(source_headers)
        headers = _table_layout(cursor, database, table, source_headers, kind == "crm")
        quoted = ", ".join(_quote(h) for h in headers); placeholders = ", ".join(["%s"] * len(headers)); insert = f"INSERT INTO {_quote(table)} ({quoted}) VALUES ({placeholders})"
        order_index = headers.index("Order ID")
        batch = []
        for row_number, raw in enumerate(rows, 2):
            values = _row_values(raw, source_headers, headers, kind == "crm")
            if values is None: summary["failed_rows"] += 1; continue
            if not values: continue
            summary["total_rows"] += 1; digest = row_hash(values)
            batch.append((values, digest))
            if len(batch) == BATCH_SIZE:
                if kind == "crm": _import_crm_batch(cursor, conn, insert, order_index, batch, summary)
                else: _import_cases_batch(cursor, conn, insert, batch, summary)
                batch = []
        if batch:
            if kind == "crm": _import_crm_batch(cursor, conn, insert, order_index, batch, summary)
            else: _import_cases_batch(cursor, conn, insert, batch, summary)
        if book: book.close()
    except Exception as error:
        if book: book.close()
        summary["status"] = "failed"; summary["error_summary"] = str(error)[:2000]
    finally:
        cursor = conn.cursor(); cursor.execute("UPDATE `durafit_portal`.`portal_import_history` SET completed_at=%s,total_rows=%s,inserted_rows=%s,skipped_rows=%s,failed_rows=%s,status=%s,error_summary=%s WHERE import_id=%s", (_now(),summary["total_rows"],summary["inserted_rows"],summary["skipped_rows"],summary["failed_rows"],summary["status"],summary["error_summary"],import_id.bytes)); conn.commit(); conn.close()
    summary["source_sheet"] = "Sales Order" if kind == "crm" and summary["status"] == "completed" else None
    return summary


def dry_run(kind: str, content: bytes) -> dict:
    """Validate and classify an upload without any write to MySQL."""
    if kind not in {"crm", "cases"}: raise ValueError("Unknown import type")
    database, table = ("durafit_crm", "crm_records") if kind == "crm" else ("durafit_cases", "case_records")
    book, source_sheet, source_headers, rows = _workbook_rows(content, "Sales Order" if kind == "crm" else None)
    try:
        find_order_id_column(source_headers)
        conn=mysql.connector.connect(**mysql_options(database=database,pool=False)); cur=conn.cursor()
        headers = _table_layout(cur, database, table, source_headers, kind == "crm")
        parsed=[]; failed=0
        for raw in rows:
            values=_row_values(raw, source_headers, headers, kind == "crm")
            if values is None: failed+=1;continue
            if values: parsed.append(values)
        order_index=headers.index('Order ID'); order_ids=sorted({r[order_index] for r in parsed if r[order_index]})
        existing=set()
        if kind=='crm' and order_ids:
            placeholders=','.join(['%s']*len(order_ids));cur.execute(f"SELECT `Order ID` FROM crm_records WHERE `Order ID` IN ({placeholders})",order_ids);existing={r[0] for r in cur.fetchall()}
        hashes={row_hash(r) for r in parsed}
        known=set()
        if kind=='cases' and hashes:
            placeholders=','.join(['%s']*len(hashes));cur.execute(f"SELECT record_hash FROM imported_record_hashes WHERE record_hash IN ({placeholders})",list(hashes));known={r[0] for r in cur.fetchall()}
        preview=[]; missing={}; seen=set(); skipped=0
        for r in parsed:
            identity = r[order_index] if kind == 'crm' else row_hash(r)
            is_skip=(identity in existing) if kind=='crm' else (identity in known)
            # Match the final importer: a duplicate later in the same workbook is skipped.
            if identity in seen: is_skip = True
            seen.add(identity)
            if not is_skip and len(preview)<50: preview.append({h:r[i] for i,h in enumerate(headers) if h in {'Order ID','Name','Account Name','Mobile Number','Invoice No','Standard Sku','SKU new','Product Type','Dispatched From','SO Status','Customer','Product','Status','Case Type'}})
            if is_skip: skipped += 1
            for i,v in enumerate(r):
                if v is None or not str(v).strip(): missing[headers[i]]=missing.get(headers[i],0)+1
        return {'import_type':kind,'source_sheet':source_sheet,'total_rows':len(parsed),'new_records':len(parsed)-skipped,'skipped_records':skipped,'failed_rows':failed,'missing_fields':missing,'preview':preview}
    finally:
        book.close();
        try: cur.close();conn.close()
        except UnboundLocalError: pass


def customer_cases(page=1, page_size=25, search='', crm_status='all', case_status='all'):
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        where=[];params=[]
        if search:
            where.append('(s.order_id LIKE %s OR s.full_name LIKE %s OR s.phone_number LIKE %s)');params += [f'%{search}%']*3
        if crm_status == 'Order ID Exists':
            where.append('EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=s.order_id)')
        elif crm_status == 'Order ID Not Found':
            where.append('NOT EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=s.order_id)')
        if case_status == 'Need to Create Case':
            where.append('NOT EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id)')
        elif case_status != 'all':
            where.append('EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id AND k.`Status`=%s)');params.append(case_status)
        clause=(' WHERE '+' AND '.join(where)) if where else ''
        cur.execute(f"SELECT COUNT(*) AS total FROM portal_submissions s{clause}",params);total=cur.fetchone()['total']
        cur.execute(f"SELECT BIN_TO_UUID(s.submission_id) submission_id,s.created_at,s.order_id,s.full_name,s.phone_number,s.crm_product_name,s.crm_purchased_product,s.issue_category,s.detailed_description FROM portal_submissions s{clause} ORDER BY s.created_at DESC LIMIT %s OFFSET %s",params+[page_size,(page-1)*page_size]);rows=cur.fetchall();ids=[r['order_id'] for r in rows]
        crm=set();statuses={}
        if ids:
            marks=','.join(['%s']*len(ids));cur.execute(f"SELECT `Order ID` FROM `durafit_crm`.`crm_records` WHERE `Order ID` IN ({marks})",ids);crm={r['Order ID'] for r in cur.fetchall()}
            cur.execute(f"SELECT `Order ID`,`Status` FROM `durafit_cases`.`case_records` WHERE `Order ID` IN ({marks})",ids)
            for r in cur.fetchall(): statuses.setdefault(r['Order ID'],[]).append(r['Status'] or 'Not Available')
        out=[]
        for row in rows:
            row['crm_status']='Order ID Exists' if row['order_id'] in crm else 'Order ID Not Found';row['case_statuses']=statuses.get(row['order_id'],['Need to Create Case'])
            out.append(row)
        cur.execute("SELECT DISTINCT `Status` AS value FROM `durafit_cases`.`case_records` WHERE `Status` IS NOT NULL AND TRIM(`Status`)<>'' ORDER BY `Status`")
        return {'items':out,'page':page,'page_size':page_size,'total':total,'case_status_options':[r['value'] for r in cur.fetchall()]}
    finally:cur.close();conn.close()


def customer_case_detail(submission_id: str) -> dict | None:
    """Read one application-owned submission and its private attachment metadata."""
    try: submission = uuid.UUID(submission_id)
    except ValueError: return None
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT BIN_TO_UUID(s.submission_id) submission_id,s.created_at,s.full_name,s.phone_number,s.alternate_number,s.order_id,s.customer_address,s.pincode,s.issue_category,s.detailed_description,s.submission_status,s.crm_product_name,s.crm_purchased_product,s.crm_sku_new,s.crm_customer_name,s.crm_mobile_number,s.crm_customer_email,p.case_id,p.case_status
        FROM portal_submissions s LEFT JOIN portal_cases p ON p.submission_id=s.submission_id WHERE s.submission_id=%s""", (submission.bytes,))
        item=cur.fetchone()
        if not item: return None
        cur.execute("SELECT BIN_TO_UUID(attachment_id) attachment_id,attachment_kind,original_filename,content_type,byte_size,created_at FROM portal_submission_attachments WHERE submission_id=%s ORDER BY display_order",(submission.bytes,));item['attachments']=cur.fetchall()
        # Product data in the list is deliberately the submission snapshot.  The
        # details view also reads this small, explicit set of current CRM fields.
        cur.execute("""SELECT `Name` AS cx_name,`Account Name` AS account_name,`Product Type` AS product_type,
            `Product Name` AS product_name,`Order Date` AS order_date,`Place of Supply` AS place_of_supply,
            `Purchased Product` AS purchased_product,`SKU new` AS sku_new
            FROM `durafit_crm`.`crm_records` WHERE `Order ID`=%s LIMIT 1""",(item['order_id'],))
        item['crm']=cur.fetchone()
        item['crm_status']='Order ID Exists' if item['crm'] else 'Order ID Not Found'
        cur.execute("SELECT `Status` FROM `durafit_cases`.`case_records` WHERE `Order ID`=%s",(item['order_id'],));item['case_statuses']=[r['Status'] or 'Not Available' for r in cur.fetchall()] or ['Need to Create Case']
        return item
    finally: cur.close();conn.close()


def attachment_path(submission_id: str, attachment_id: str):
    """Resolve a private attachment only after its submission relationship is checked."""
    try: submission=uuid.UUID(submission_id); attachment=uuid.UUID(attachment_id)
    except ValueError: return None
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT storage_key,original_filename,content_type FROM portal_submission_attachments WHERE submission_id=%s AND attachment_id=%s",(submission.bytes,attachment.bytes));return cur.fetchone()
    finally: cur.close();conn.close()


def stats_and_history(limit=50):
    options = mysql_options(database="durafit_portal", pool=False); conn = mysql.connector.connect(**options); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT COUNT(*) AS value FROM `durafit_crm`.`crm_records`"); crm = cur.fetchone()["value"]
        cur.execute("SELECT COUNT(*) AS value FROM `durafit_cases`.`case_records`"); cases = cur.fetchone()["value"]
        cur.execute("SELECT COUNT(*) AS value FROM portal_submissions"); customer_cases = cur.fetchone()["value"]
        cur.execute("""SELECT COALESCE(NULLIF(TRIM(`Status`),''),'Not Available') AS status, COUNT(*) AS count
            FROM `durafit_cases`.`case_records` GROUP BY COALESCE(NULLIF(TRIM(`Status`),''),'Not Available') ORDER BY count DESC, status""")
        case_status_breakdown = cur.fetchall()
        cur.execute("""SELECT
            COALESCE(SUM(CASE WHEN EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id) THEN 1 ELSE 0 END),0) AS order_id_exists,
            COALESCE(SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id) THEN 1 ELSE 0 END),0) AS need_to_create_case
            FROM portal_submissions s""")
        customer_case_breakdown = {key: int(value or 0) for key, value in cur.fetchone().items()}
        cur.execute("""SELECT
            COALESCE(SUM(CASE WHEN EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=TRIM(s.order_id)) THEN 1 ELSE 0 END),0) AS order_id_exists,
            COALESCE(SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=TRIM(s.order_id)) THEN 1 ELSE 0 END),0) AS order_id_not_found
            FROM portal_submissions s""")
        crm_status_breakdown = {key: int(value or 0) for key, value in cur.fetchone().items()}
        cur.execute("SELECT import_type, completed_at, status FROM portal_import_history WHERE status='completed' ORDER BY completed_at DESC"); rows=cur.fetchall()
        last = {r["import_type"]: r for r in rows if r["import_type"] not in {x for x in []}}
        # Preserve most recent entry for each import type.
        latest={}; [latest.setdefault(r["import_type"], r) for r in rows]
        return {"crm_records":crm,"case_records":cases,"cases_records":cases,"customer_cases":customer_cases,
                "last_crm_import":latest.get("crm"),"last_cases_import":latest.get("cases"),
                "case_status_breakdown":case_status_breakdown,
                "customer_case_breakdown":customer_case_breakdown,
                "crm_status_breakdown":crm_status_breakdown}
    finally: cur.close(); conn.close()


def history(limit=50):
    options=mysql_options(database="durafit_portal",pool=False); conn=mysql.connector.connect(**options); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT BIN_TO_UUID(import_id) AS import_id,import_type,original_filename,started_at,completed_at,total_rows,inserted_rows,skipped_rows,failed_rows,status,error_summary FROM portal_import_history ORDER BY created_at DESC LIMIT %s", (min(max(limit,1),100),)); return cur.fetchall()
    finally: cur.close();conn.close()


def customer_submissions(page=1, page_size=25, search='', crm_status='all', case_status='all', submission_status='all'):
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        where=[];params=[]
        if search:
            where.append('(s.order_id LIKE %s OR s.full_name LIKE %s OR s.phone_number LIKE %s)');params += [f'%{search}%']*3
        if crm_status == 'Order ID Exists':
            where.append('EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=s.order_id)')
        elif crm_status == 'Order ID Not Found':
            where.append('NOT EXISTS (SELECT 1 FROM `durafit_crm`.`crm_records` c WHERE c.`Order ID`=s.order_id)')
        if case_status == 'Need to Create Case':
            where.append('NOT EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id)')
        elif case_status != 'all':
            where.append('EXISTS (SELECT 1 FROM `durafit_cases`.`case_records` k WHERE k.`Order ID`=s.order_id AND k.`Status`=%s)');params.append(case_status)
        if submission_status in ('pending_verification', 'Pending Verification'):
            where.append("s.submission_status IN ('pending_verification', 'received')")
        elif submission_status in ('moved_to_cases', 'Moved to Cases'):
            where.append("s.submission_status = 'moved_to_cases'")
        elif submission_status != 'all':
            where.append("s.submission_status = %s");params.append(submission_status)
        clause=(' WHERE '+' AND '.join(where)) if where else ''
        cur.execute(f"SELECT COUNT(*) AS total FROM portal_submissions s{clause}",params);total=cur.fetchone()['total']
        cur.execute(f"""SELECT BIN_TO_UUID(s.submission_id) submission_id,s.created_at,s.order_id,s.full_name,s.phone_number,
                       s.alternate_number,s.customer_address,s.pincode,s.crm_product_name,s.crm_purchased_product,
                       s.issue_category,s.detailed_description,s.submission_status
                       FROM portal_submissions s{clause} ORDER BY s.created_at DESC LIMIT %s OFFSET %s""",
                    params+[page_size,(page-1)*page_size])
        rows=cur.fetchall();ids=[r['order_id'] for r in rows]
        crm=set();statuses={}
        if ids:
            marks=','.join(['%s']*len(ids));cur.execute(f"SELECT `Order ID` FROM `durafit_crm`.`crm_records` WHERE `Order ID` IN ({marks})",ids);crm={r['Order ID'] for r in cur.fetchall()}
            cur.execute(f"SELECT `Order ID`,`Status` FROM `durafit_cases`.`case_records` WHERE `Order ID` IN ({marks})",ids)
            for r in cur.fetchall(): statuses.setdefault(r['Order ID'],[]).append(r['Status'] or 'Not Available')
        out=[]
        for row in rows:
            row['crm_status']='Order ID Exists' if row['order_id'] in crm else 'Order ID Not Found'
            row['case_statuses']=statuses.get(row['order_id'],['Need to Create Case'])
            raw_st = row.get('submission_status') or 'pending_verification'
            row['submission_status_display'] = 'Moved to Cases' if raw_st == 'moved_to_cases' else 'Pending Verification'
            out.append(row)
        cur.execute("SELECT DISTINCT `Status` AS value FROM `durafit_cases`.`case_records` WHERE `Status` IS NOT NULL AND TRIM(`Status`)<>'' ORDER BY `Status`")
        return {'items':out,'page':page,'page_size':page_size,'total':total,'case_status_options':[r['value'] for r in cur.fetchall()]}
    finally:cur.close();conn.close()


def update_customer_submission(submission_id: str, fields: dict) -> dict | None:
    try: submission = uuid.UUID(submission_id)
    except ValueError: return None
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT BIN_TO_UUID(submission_id) sub_id, order_id FROM portal_submissions WHERE submission_id=%s", (submission.bytes,))
        existing = cur.fetchone()
        if not existing:
            return None
        new_order_id = fields.get('order_id', existing['order_id']).strip()
        cur.execute("""SELECT `Order ID`, `Product Name`, `Purchased Product`, `SKU new`, `Name`, `Mobile Number`, `Customer Email`, `Sales Order Owner`
                       FROM `durafit_crm`.`crm_records` WHERE `Order ID` = %s LIMIT 1""", (new_order_id,))
        crm_snap = cur.fetchone()

        cur.execute("""
            UPDATE portal_submissions
            SET full_name = %s,
                phone_number = %s,
                alternate_number = %s,
                order_id = %s,
                customer_address = %s,
                pincode = %s,
                issue_category = %s,
                detailed_description = %s,
                crm_order_id = %s,
                crm_product_name = %s,
                crm_purchased_product = %s,
                crm_sku_new = %s,
                crm_customer_name = %s,
                crm_mobile_number = %s,
                crm_customer_email = %s,
                crm_sales_order_owner = %s,
                updated_at = NOW(6)
            WHERE submission_id = %s
        """, (
            fields['full_name'].strip(),
            fields['phone_number'].strip(),
            (fields.get('alternate_number') or '').strip() or None,
            new_order_id,
            fields['customer_address'].strip(),
            fields['pincode'].strip(),
            fields['issue_category'].strip(),
            fields['detailed_description'].strip(),
            crm_snap['Order ID'] if crm_snap else None,
            crm_snap['Product Name'] if crm_snap else None,
            crm_snap['Purchased Product'] if crm_snap else None,
            crm_snap['SKU new'] if crm_snap else None,
            crm_snap['Name'] if crm_snap else None,
            crm_snap['Mobile Number'] if crm_snap else None,
            crm_snap['Customer Email'] if crm_snap else None,
            crm_snap['Sales Order Owner'] if crm_snap else None,
            submission.bytes,
        ))
        cur.execute("""
            INSERT INTO portal_submission_events (submission_id, case_id, event_type, event_payload, created_at)
            VALUES (%s, NULL, 'submission_edited_by_admin', %s, NOW(6))
        """, (submission.bytes, json.dumps({"updated_fields": list(fields.keys())})))
        conn.commit()
    finally:
        cur.close(); conn.close()
    return customer_case_detail(submission_id)


def move_submission_to_cases_placeholder(submission_id: str) -> dict | None:
    try: submission = uuid.UUID(submission_id)
    except ValueError: return None
    conn=mysql.connector.connect(**mysql_options(database='durafit_portal',pool=False));cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT BIN_TO_UUID(submission_id) sub_id, order_id, submission_status FROM portal_submissions WHERE submission_id=%s", (submission.bytes,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "success": True,
            "submission_id": submission_id,
            "order_id": row["order_id"],
            "status": "ready_for_case_creation",
            "message": "Move to Cases action triggered. Case creation will be executed in Step 3."
        }
    finally:
        cur.close(); conn.close()

