"""Minimal read-only FastAPI service for customer order verification."""

from contextlib import asynccontextmanager

import mysql.connector
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from src.portal_db import close_pool, find_order
from src.portal_models import OrderLookupResponse, SubmissionResponse, SubmissionUpdateRequest
from src.portal_submissions import create_submission
from src.admin_auth import authenticate, require_admin, revoke
from src.admin_imports import (
    attachment_path, customer_case_detail, customer_cases, customer_submissions,
    dry_run, history as import_history, import_xlsx, move_submission_to_cases as admin_move_submission_to_cases,
    move_submission_to_cases_placeholder, stats_and_history, update_customer_submission,
)
from src.portal_submissions import STORAGE_ROOT


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_pool()


app = FastAPI(title="Durafit91 Customer Portal API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "https://durafit91-portal.onrender.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.post("/api/admin/login")
def admin_login(username: str = Form(...), password: str = Form(...)) -> dict[str, str]:
    token = authenticate(username, password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"token": token}


@app.post("/api/admin/logout")
def admin_logout(authorization: str | None = Header(default=None), _: str = Depends(require_admin)) -> dict[str, bool]:
    revoke(authorization)
    return {"success": True}


@app.post("/api/admin/import/crm")
async def import_crm(file: UploadFile = File(...), _: str = Depends(require_admin)) -> dict:
    return import_xlsx("crm", file.filename or "upload.xlsx", await file.read())

@app.post("/api/admin/import/crm/dry-run")
async def dry_run_crm(file: UploadFile = File(...), _: str = Depends(require_admin)) -> dict:
    try: return dry_run("crm", await file.read())
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error))


@app.post("/api/admin/import/cases")
async def import_cases(file: UploadFile = File(...), _: str = Depends(require_admin)) -> dict:
    return import_xlsx("cases", file.filename or "upload.xlsx", await file.read())

@app.post("/api/admin/import/cases/dry-run")
async def dry_run_cases(file: UploadFile = File(...), _: str = Depends(require_admin)) -> dict:
    try: return dry_run("cases", await file.read())
    except ValueError as error: raise HTTPException(status_code=422, detail=str(error))

@app.get("/api/admin/customer-cases")
def list_customer_cases(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), search: str = "", crm_status: str = "all", case_status: str = "all", _: str = Depends(require_admin)) -> dict:
    return customer_cases(page, page_size, search.strip(), crm_status, case_status)

@app.get("/api/admin/customer-cases/{submission_id}")
def get_customer_case(submission_id: str, _: str = Depends(require_admin)) -> dict:
    result = customer_case_detail(submission_id)
    if result is None: raise HTTPException(status_code=404, detail="Customer submission not found")
    return result

@app.get("/api/admin/customer-cases/{submission_id}/attachments/{attachment_id}")
def get_customer_attachment(submission_id: str, attachment_id: str, _: str = Depends(require_admin)):
    record = attachment_path(submission_id, attachment_id)
    if record is None: raise HTTPException(status_code=404, detail="Attachment not found")
    path = (STORAGE_ROOT / record['storage_key']).resolve()
    if STORAGE_ROOT.resolve() not in path.parents or not path.is_file(): raise HTTPException(status_code=404, detail="Attachment file is unavailable")
    return FileResponse(path, media_type=record['content_type'] or 'application/octet-stream', filename=record['original_filename'])


@app.get("/api/admin/customer-submissions")
def list_customer_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = "",
    crm_status: str = "all",
    case_status: str = "all",
    submission_status: str = "all",
    _: str = Depends(require_admin),
) -> dict:
    return customer_submissions(page, page_size, search.strip(), crm_status, case_status, submission_status)


@app.get("/api/admin/customer-submissions/{submission_id}")
def get_customer_submission(submission_id: str, _: str = Depends(require_admin)) -> dict:
    result = customer_case_detail(submission_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer submission not found")
    return result


@app.put("/api/admin/customer-submissions/{submission_id}")
def put_customer_submission(submission_id: str, body: SubmissionUpdateRequest, _: str = Depends(require_admin)) -> dict:
    result = update_customer_submission(submission_id, body.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Customer submission not found")
    return result


@app.post("/api/admin/customer-submissions/{submission_id}/move-to-cases")
def move_submission_to_cases(submission_id: str, admin: str = Depends(require_admin)) -> dict:
    result = admin_move_submission_to_cases(submission_id, admin_user=admin)
    if result is None:
        raise HTTPException(status_code=404, detail="Customer submission not found")
    return result


@app.get("/api/admin/customer-submissions/{submission_id}/attachments/{attachment_id}")
def get_submission_attachment(submission_id: str, attachment_id: str, _: str = Depends(require_admin)):
    record = attachment_path(submission_id, attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = (STORAGE_ROOT / record['storage_key']).resolve()
    if STORAGE_ROOT.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is unavailable")
    return FileResponse(path, media_type=record['content_type'] or 'application/octet-stream', filename=record['original_filename'])


@app.get("/api/admin/import/history")
def get_import_history(_: str = Depends(require_admin)) -> list[dict]:
    return import_history()


@app.get("/api/admin/stats")
def admin_stats(_: str = Depends(require_admin)) -> dict:
    return stats_and_history()


@app.get("/api/orders/{order_id}", response_model=OrderLookupResponse)
def get_order(order_id: str) -> OrderLookupResponse:
    """Return approved CRM details for an exact Order ID, or a 404."""
    if not order_id:
        raise HTTPException(status_code=404, detail="Order ID not found")
    try:
        record = find_order(order_id)
    except (mysql.connector.Error, RuntimeError):
        # Do not disclose connection details or credentials to API clients.
        raise HTTPException(status_code=503, detail="Order lookup is temporarily unavailable")
    if record is None:
        raise HTTPException(status_code=404, detail="Order ID not found")
    return OrderLookupResponse(
        order_id=record["Order ID"], cx_name=record["Name"], account_name=record["Account Name"],
        product_type=record["Product Type"], product_name=record["Product Name"], order_date=record["Order Date"],
        place_of_supply=record["Place of Supply"], purchased_product=record["Purchased Product"],
        sku_new=record["SKU new"], name=record["Name"], mobile_number=record["Mobile Number"],
        customer_email=record["Customer Email"],
    )


@app.post("/api/submissions", response_model=SubmissionResponse)
async def submit_request(
    idempotency_key: str = Form(...), full_name: str = Form(...), phone: str = Form(...),
    alternate_number: str = Form(""), order_id: str = Form(...), customer_address: str = Form(...),
    state: str | None = Form(None), pincode: str = Form(...), issue_category: str = Form(...), subject: str | None = Form(None),
    description: str = Form(...), invoice_image: UploadFile = File(...), attachments: list[UploadFile] = File(default=[]),
) -> SubmissionResponse:
    fields = {"full_name": full_name.strip(), "phone": phone.strip(), "alternate_number": alternate_number.strip(),
              "order_id": order_id.strip(), "customer_address": customer_address.strip(), "state": state.strip() if state else None,
              "pincode": pincode.strip(), "issue_category": issue_category.strip(), "subject": subject.strip() if subject else None, "description": description.strip()}
    if any(not value for key, value in fields.items() if key not in {"alternate_number", "state", "subject"}):
        raise HTTPException(status_code=422, detail="All required fields must be provided")
    try:
        result = await create_submission(fields, invoice_image, attachments, idempotency_key)
    except HTTPException:
        raise
    except mysql.connector.Error:
        raise HTTPException(status_code=503, detail="Submission service is temporarily unavailable")
    return SubmissionResponse(success=True, submission_id=result["submission_id"], case_id=result.get("case_id"), status=result["status"], message="Your service request has been submitted successfully.")
