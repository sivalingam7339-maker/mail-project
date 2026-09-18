"""Response models for the read-only customer portal API."""

from pydantic import BaseModel


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
    case_id: str
    status: str
    message: str
