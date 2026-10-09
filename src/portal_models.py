"""Response models for the read-only customer portal API."""

from pydantic import BaseModel, ConfigDict


class OrderLookupResponse(BaseModel):
    """Only the CRM fields approved for the customer portal."""

    order_id: str
    cx_name: str | None = None
    account_name: str | None = None
    product_type: str | None = None
    product_name: str | None = None
    order_date: str | None = None
    place_of_supply: str | None = None
    purchased_product: str | None = None
    sku_new: str | None = None
    name: str | None = None
    mobile_number: str | None = None
    customer_email: str | None = None


class SubmissionResponse(BaseModel):
    success: bool
    submission_id: str
    case_id: str | None = None
    status: str
    message: str


class SubmissionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    full_name: str
    phone_number: str
    alternate_number: str | None = None
    order_id: str
    customer_address: str
    pincode: str
    issue_category: str
    detailed_description: str
    case_id: str | None = None
    sku: str | None = None
    product: str | None = None
    case_type: str | None = None
    status: str | None = None
    spares: str | None = None
    comment: str | None = None
    so_owner: str | None = None
    welcome_call_agent: str | None = None
    created_by: str | None = None
    created_date: str | None = None
    closed_date: str | None = None
    visit_status: str | None = None
    amount_charged: str | None = None
    amount_to_tech: str | None = None
    technician_resolution: str | None = None
