"""Transactional submission creation and safe private attachment storage."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

import mysql.connector
from fastapi import HTTPException, UploadFile

from src.portal_db import mysql_options


STORAGE_ROOT = Path(r"C:\Mail\storage\portal-submissions")
MAX_INVOICE_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS = 5
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
INVOICE_TYPES = {"image/jpeg", "image/png", "image/webp"}
OTHER_TYPES = INVOICE_TYPES | {"application/pdf", "video/mp4", "video/quicktime", "video/webm"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uuid_bytes(value: uuid.UUID) -> bytes:
    return value.bytes


def _case_id() -> str:
    return f"DF91-CASE-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:4].upper()}"


def _safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    cleaned = SAFE_FILENAME.sub("_", base).strip("._")
    if not cleaned:
        raise HTTPException(status_code=422, detail="Invalid attachment filename")
    return cleaned[:200]


async def _store_file(file: UploadFile, directory: Path, kind: str, order: int, limit: int, allowed: set[str]) -> dict:
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(status_code=422, detail="Unsupported attachment type")
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if not suffix:
        raise HTTPException(status_code=422, detail="Attachment filename must include an extension")
    target_name = f"{kind}-{order:02d}-{uuid.uuid4().hex}{suffix}"
    target = directory / target_name
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=422, detail="Attachment exceeds the allowed size")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {"attachment_id": _uuid_bytes(uuid.uuid4()), "kind": kind, "display_order": order,
            "storage_key": f"{directory.name}/{target_name}", "filename": filename, "content_type": content_type,
            "size": size, "sha256": digest.digest()}


def _crm_snapshot(cursor, order_id: str) -> dict | None:
    cursor.execute("""SELECT `Order ID`, `Product Name`, `Purchased Product`, `SKU new`, `Name`, `Mobile Number`, `Customer Email`, `Sales Order Owner`
                      FROM `durafit_crm`.`crm_records` WHERE `Order ID` = %s LIMIT 1""", (order_id,))
    return cursor.fetchone()


def _existing(cursor, idempotency_key: str) -> dict | None:
    cursor.execute("""SELECT BIN_TO_UUID(s.submission_id) AS submission_id, c.case_id, s.submission_status
                      FROM `portal_submissions` s JOIN `portal_cases` c ON c.submission_id=s.submission_id
                      WHERE s.idempotency_key=%s""", (idempotency_key,))
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return {"submission_id": row["submission_id"], "case_id": row["case_id"], "status": row["submission_status"]}
    return {"submission_id": row[0], "case_id": row[1], "status": row[2]}


async def create_submission(fields: dict[str, str], invoice_image: UploadFile | None, attachments: list[UploadFile], idempotency_key: str) -> dict:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", idempotency_key):
        raise HTTPException(status_code=422, detail="Invalid idempotency key")
    if invoice_image is None:
        raise HTTPException(status_code=422, detail="Invoice image is required")
    if len(attachments) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=422, detail="A maximum of five attachments is allowed")
    order_id = fields["order_id"].strip()
    options = mysql_options(database="durafit_portal", pool=False)
    conn = mysql.connector.connect(**options)
    directory: Path | None = None
    try:
        cursor = conn.cursor(dictionary=True)
        existing = _existing(cursor, idempotency_key)
        if existing:
            return {**existing, "replayed": True}
        snapshot = _crm_snapshot(cursor, order_id)
        submission_uuid = uuid.uuid4()
        submission_id = _uuid_bytes(submission_uuid)
        directory = STORAGE_ROOT / str(submission_uuid)
        directory.mkdir(parents=True, exist_ok=False)
        stored = [await _store_file(invoice_image, directory, "invoice_image", 1, MAX_INVOICE_BYTES, INVOICE_TYPES)]
        for number, upload in enumerate(attachments, 1):
            kind = "product_image" if (upload.content_type or "").lower() in INVOICE_TYPES else "supporting_attachment"
            stored.append(await _store_file(upload, directory, kind, number, MAX_ATTACHMENT_BYTES, OTHER_TYPES))
        case_id = _case_id()
        now = _now()
        conn.start_transaction()
        cursor.execute("""INSERT INTO portal_submissions
          (submission_id,idempotency_key,crm_order_id,crm_product_name,crm_purchased_product,crm_sku_new,crm_customer_name,crm_mobile_number,crm_customer_email,crm_sales_order_owner,full_name,email_address,phone_number,alternate_number,order_id,customer_address,state,pincode,issue_category,subject,detailed_description,submission_status,created_at,updated_at)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,'received',%s,%s)""",
          (submission_id,idempotency_key,snapshot["Order ID"] if snapshot else None,snapshot["Product Name"] if snapshot else None,snapshot["Purchased Product"] if snapshot else None,snapshot["SKU new"] if snapshot else None,snapshot["Name"] if snapshot else None,snapshot["Mobile Number"] if snapshot else None,snapshot["Customer Email"] if snapshot else None,snapshot["Sales Order Owner"] if snapshot else None,fields["full_name"],fields["phone"],fields.get("alternate_number") or None,order_id,fields["customer_address"],fields.get("state"),fields["pincode"],fields["issue_category"],fields.get("subject"),fields["description"],now,now))
        cursor.execute("INSERT INTO portal_cases (case_id,submission_id,crm_order_id,case_status,created_at,updated_at) VALUES (%s,%s,%s,'received',%s,%s)", (case_id,submission_id,snapshot["Order ID"] if snapshot else None,now,now))
        cursor.executemany("""INSERT INTO portal_submission_attachments (attachment_id,submission_id,attachment_kind,display_order,storage_key,original_filename,content_type,byte_size,sha256,upload_status,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'stored',%s)""", [(item["attachment_id"],submission_id,item["kind"],item["display_order"],item["storage_key"],item["filename"],item["content_type"],item["size"],item["sha256"],now) for item in stored])
        cursor.execute("INSERT INTO portal_submission_events (submission_id,case_id,event_type,event_payload,created_at) VALUES (%s,%s,'submission_created',%s,%s)", (submission_id,case_id,json.dumps({"attachment_count": len(stored)}),now))
        cursor.execute("INSERT INTO portal_email_outbox (outbox_id,submission_id,message_type,delivery_status) VALUES (%s,%s,'customer_confirmation','pending')", (_uuid_bytes(uuid.uuid4()),submission_id))
        conn.commit()
        return {"submission_id": str(submission_uuid), "case_id": case_id, "status": "received", "replayed": False}
    except mysql.connector.IntegrityError:
        conn.rollback()
        cursor = conn.cursor(dictionary=True)
        existing = _existing(cursor, idempotency_key)
        if existing:
            return {**existing, "replayed": True}
        raise
    except Exception:
        conn.rollback()
        if directory:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        conn.close()
