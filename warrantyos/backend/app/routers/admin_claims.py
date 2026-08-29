"""
Admin Claim APIs — Part 1.2
Exposes customer/product/serial/warranty/evidence/timeline with filtering.
"""

from typing import Optional, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, Customer
from app.models.product import Product, ProductSerial
from app.models.claim import Claim, ClaimEvidence, ClaimTimeline
from app.schemas.claim import ClaimOut, ClaimDetailOut

router = APIRouter(prefix="/api/admin/claims", tags=["admin-claims"])


def _to_claim_out(claim: Claim) -> ClaimOut:
    from app.schemas.claim import WarrantyOut
    warranty = None
    if claim.warranty_eligible is not None:
        warranty = WarrantyOut(
            eligible=claim.warranty_eligible,
            warranty_active=bool(claim.warranty_eligible),
            policy_match=not (claim.exclusions_triggered and len(claim.exclusions_triggered) > 0),
            reason=claim.eligibility_reason or "",
            exclusions_triggered=claim.exclusions_triggered or [],
            missing_information=claim.missing_information or [],
            purchase_date=claim.purchase_date,
        )
    return ClaimOut(
        id=claim.id,
        claim_code=claim.claim_code,
        customer_id=claim.customer_id,
        product_id=claim.product_id,
        serial_id=claim.serial_id,
        retailer_id=claim.retailer_id,
        fault_description=claim.fault_description,
        fault_category=claim.fault_category,
        status=claim.status,
        purchase_date=claim.purchase_date,
        warranty_eligible=claim.warranty_eligible,
        eligibility_reason=claim.eligibility_reason,
        warranty_checked_at=claim.warranty_checked_at,
        exclusions_triggered=claim.exclusions_triggered,
        missing_information=claim.missing_information,
        ai_analysis_status=claim.ai_analysis_status or "PENDING",
        ai_analysis_requested_at=claim.ai_analysis_requested_at,
        ai_analysis_completed_at=claim.ai_analysis_completed_at,
        ai_analysis_error=claim.ai_analysis_error,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        warranty=warranty,
    )


def _to_detail_out(db: Session, claim: Claim) -> ClaimDetailOut:
    from app.schemas.claim import ProductOut, SerialOut, CustomerOut, EvidenceOut, TimelineEventOut
    base = _to_claim_out(claim)
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
    cust = db.query(Customer).filter(Customer.id == claim.customer_id).first()
    prod_out = ProductOut.model_validate(product) if product else None
    serial_out = SerialOut.model_validate(serial) if serial else None
    cust_out = None
    if cust:
        u = db.query(User).filter(User.id == cust.user_id).first()
        cust_out = CustomerOut(id=cust.id, user_id=cust.user_id, full_name=u.full_name if u else "", email=u.email if u else "")
    evidence = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).order_by(ClaimEvidence.uploaded_at.desc()).all()
    timeline = db.query(ClaimTimeline).filter(ClaimTimeline.claim_id == claim.id).order_by(ClaimTimeline.created_at.asc()).all()
    return ClaimDetailOut(
        **base.model_dump(),
        product=prod_out,
        serial=serial_out,
        customer=cust_out,
        evidence=[EvidenceOut.model_validate(e) for e in evidence],
        timeline=[TimelineEventOut.model_validate(t) for t in timeline],
    )


@router.get("", response_model=List[ClaimOut])
def list_admin_claims(
    status: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    q = db.query(Claim)
    if status:
        status = status.upper()
        q = q.filter(Claim.status == status)
    if product_id:
        q = q.filter(Claim.product_id == product_id)
    if customer_id:
        q = q.filter(Claim.customer_id == customer_id)
    if date_from:
        q = q.filter(Claim.created_at >= date_from)
    if date_to:
        q = q.filter(Claim.created_at <= date_to)
    claims = q.order_by(Claim.created_at.desc()).all()
    return [_to_claim_out(c) for c in claims]


@router.get("/{claim_id}", response_model=ClaimDetailOut)
def get_admin_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return _to_detail_out(db, claim)
