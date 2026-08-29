from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# --- Request ---

class ClaimCreateRequest(BaseModel):
    product_id: int
    serial_number: Optional[str] = Field(None, description="Physical unit serial number")
    retailer_id: Optional[int] = None
    fault_description: str = Field(min_length=10, max_length=5000)
    fault_category: Optional[str] = Field(None, max_length=100)
    purchase_date: Optional[date] = None  # override serial's date if provided


class StatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="Target status, e.g., PROCESSING")
    notes: Optional[str] = None


# --- Response ---

class ProductOut(BaseModel):
    id: int
    name: str
    sku: str
    category: str
    manufacturer: Optional[str] = None
    warranty_period_months: int

    class Config:
        from_attributes = True


class SerialOut(BaseModel):
    id: int
    serial_number: str
    purchase_date: Optional[date] = None
    product_id: int

    class Config:
        from_attributes = True


class CustomerOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str

    class Config:
        from_attributes = True


class EvidenceOut(BaseModel):
    id: int
    claim_id: int
    evidence_type: str
    original_filename: Optional[str] = None
    stored_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    description: Optional[str] = None
    uploaded_at: datetime
    # file_path is internal, not exposed directly

    class Config:
        from_attributes = True


class TimelineEventOut(BaseModel):
    id: int
    claim_id: int
    event_type: str
    actor: Optional[str] = None
    notes: Optional[str] = None
    event_metadata: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WarrantyOut(BaseModel):
    eligible: bool
    warranty_active: bool
    policy_match: bool
    reason: str
    exclusions_triggered: List[str] = []
    missing_information: List[str] = []
    purchase_date: Optional[date] = None
    warranty_end_date: Optional[date] = None


class ClaimOut(BaseModel):
    id: int
    claim_code: str
    customer_id: int
    product_id: int
    serial_id: Optional[int] = None
    retailer_id: Optional[int] = None
    fault_description: str
    fault_category: Optional[str] = None
    status: str
    purchase_date: Optional[date] = None
    warranty_eligible: Optional[bool] = None
    eligibility_reason: Optional[str] = None
    warranty_checked_at: Optional[datetime] = None
    exclusions_triggered: Optional[List[str]] = None
    missing_information: Optional[List[str]] = None
    ai_analysis_status: Optional[str] = None
    ai_analysis_requested_at: Optional[datetime] = None
    ai_analysis_completed_at: Optional[datetime] = None
    ai_analysis_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # warranty verification structured (derived from stored fields)
    warranty: Optional[WarrantyOut] = None

    class Config:
        from_attributes = True


class ClaimDetailOut(ClaimOut):
    product: Optional[ProductOut] = None
    serial: Optional[SerialOut] = None
    customer: Optional[CustomerOut] = None
    evidence: List[EvidenceOut] = []
    timeline: List[TimelineEventOut] = []


class ClaimListOut(BaseModel):
    claims: List[ClaimOut]
    total: int
