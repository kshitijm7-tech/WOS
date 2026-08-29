"""
Customer-facing Claim APIs — Part 1.2
No AI, deterministic warranty only.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, Customer
from app.models.product import Product, ProductSerial, WarrantyPolicy
from app.models.claim import Claim, ClaimEvidence, ClaimTimeline
from app.schemas.claim import (
    ClaimCreateRequest,
    ClaimOut,
    ClaimDetailOut,
    EvidenceOut,
    TimelineEventOut,
    StatusUpdateRequest,
    WarrantyOut,
)
from app.services.warranty_rules import evaluate_warranty
from app.services.status_machine import assert_valid_transition
from app.services.storage import save_upload, delete_file

router = APIRouter(prefix="/api/claims", tags=["claims"])


def _get_customer(db: Session, user: User) -> Customer:
    cust = db.query(Customer).filter(Customer.user_id == user.id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer profile not found.")
    return cust


def _get_claim_or_404(db: Session, claim_id: int) -> Claim:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def _verify_claim_access(claim: Claim, user: User, db: Session):
    """IDOR protection: customer can only access own claims; admin/support can access all."""
    if user.role.name in ("admin", "support"):
        return
    cust = _get_customer(db, user)
    if claim.customer_id != cust.id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this claim.")


def _to_claim_out(claim: Claim) -> ClaimOut:
    # Build warranty structured from stored fields
    warranty = None
    if claim.warranty_eligible is not None:
        warranty = WarrantyOut(
            eligible=claim.warranty_eligible,
            warranty_active=claim.warranty_eligible if claim.eligibility_reason and "Warranty active" in claim.eligibility_reason else bool(claim.warranty_eligible),
            policy_match=not (claim.exclusions_triggered and len(claim.exclusions_triggered) > 0),
            reason=claim.eligibility_reason or "",
            exclusions_triggered=claim.exclusions_triggered or [],
            missing_information=claim.missing_information or [],
            purchase_date=claim.purchase_date,
            warranty_end_date=None,
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
    base = _to_claim_out(claim)
    # Eager load related
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
    cust = db.query(Customer).filter(Customer.id == claim.customer_id).first()
    # Build nested
    from app.schemas.claim import ProductOut, SerialOut, CustomerOut
    prod_out = ProductOut.model_validate(product) if product else None
    serial_out = SerialOut.model_validate(serial) if serial else None
    cust_out = None
    if cust:
        # fetch user for email/name
        from app.models.user import User as UserM
        u = db.query(UserM).filter(UserM.id == cust.user_id).first()
        cust_out = CustomerOut(id=cust.id, user_id=cust.user_id, full_name=u.full_name if u else "", email=u.email if u else "")
    evidence = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).order_by(ClaimEvidence.uploaded_at.desc()).all()
    timeline = db.query(ClaimTimeline).filter(ClaimTimeline.claim_id == claim.id).order_by(ClaimTimeline.created_at.asc()).all()
    ev_out = [EvidenceOut.model_validate(e) for e in evidence]
    tl_out = [TimelineEventOut.model_validate(t) for t in timeline]
    # Merge base
    detail = ClaimDetailOut(
        **base.model_dump(),
        product=prod_out,
        serial=serial_out,
        customer=cust_out,
        evidence=ev_out,
        timeline=tl_out,
    )
    return detail


@router.post("", response_model=ClaimDetailOut, status_code=201)
def create_claim(
    payload: ClaimCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    """
    Customer creates claim. Validates product/serial/ownership, runs WarrantyRuleEngine,
    creates claim + timeline atomically.
    """
    cust = _get_customer(db, current_user)

    # 1. Product exists
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if not product.is_active:
        raise HTTPException(status_code=422, detail="Product is not active for warranty.")

    # 2. Serial handling
    serial = None
    if payload.serial_number:
        serial = db.query(ProductSerial).filter(ProductSerial.serial_number == payload.serial_number).first()
        if not serial:
            raise HTTPException(status_code=404, detail="Serial number not found.")
        # Check serial belongs to product
        if serial.product_id != product.id:
            raise HTTPException(status_code=422, detail="Serial number does not belong to this product.")
        # 3. Ownership
        if serial.owner_customer_id is not None and serial.owner_customer_id != cust.id:
            raise HTTPException(status_code=403, detail="This product serial is not owned by you.")

    # If serial not provided, try to find owner's serial for this product? Not required in 1.2 — allow no serial, but then purchase_date must be provided
    # 4. Purchase date
    purchase_date = payload.purchase_date
    if not purchase_date and serial:
        purchase_date = serial.purchase_date

    # 5. Policy
    policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == product.id).first()

    # Evaluate warranty
    result = evaluate_warranty(
        product=product,
        serial=serial,
        policy=policy,
        customer_id=cust.id,
        fault_description=payload.fault_description,
        fault_category=payload.fault_category,
        purchase_date_override=purchase_date,
    )

    # Create claim transactionally
    try:
        # Generate claim_code after flush: need id
        claim = Claim(
            claim_code="TEMP",
            customer_id=cust.id,
            product_id=product.id,
            serial_id=serial.id if serial else None,
            retailer_id=payload.retailer_id or (serial.sold_by_retailer_id if serial else None),
            fault_description=payload.fault_description.strip(),
            fault_category=payload.fault_category,
            status="SUBMITTED",
            purchase_date=result.purchase_date,
            warranty_eligible=result.eligible,
            eligibility_reason=result.reason,
            warranty_checked_at=datetime.now(timezone.utc),
            exclusions_triggered=result.exclusions_triggered,
            missing_information=result.missing_information,
        )
        db.add(claim)
        db.flush()  # get claim.id
        # Generate code like WR-10001
        claim.claim_code = f"WR-{10000 + claim.id}"
        # Timeline: CLAIM_CREATED
        tl = ClaimTimeline(
            claim_id=claim.id,
            event_type="CLAIM_CREATED",
            actor=f"customer:{current_user.email}",
            notes=f"Claim {claim.claim_code} created. Warranty: {result.reason}",
            event_metadata={
                "warranty_eligible": result.eligible,
                "reason": result.reason,
                "exclusions": result.exclusions_triggered,
                "missing": result.missing_information,
                "purchase_date": str(result.purchase_date) if result.purchase_date else None,
            },
        )
        db.add(tl)
        # Also WARRANTY_CHECKED
        tl2 = ClaimTimeline(
            claim_id=claim.id,
            event_type="WARRANTY_CHECKED",
            actor="system",
            notes=result.reason,
            event_metadata={
                "eligible": result.eligible,
                "warranty_active": result.warranty_active,
                "policy_match": result.policy_match,
            },
        )
        db.add(tl2)
        db.commit()
        db.refresh(claim)
    except Exception:
        db.rollback()
        # Don't expose DB errors
        raise HTTPException(status_code=500, detail="Failed to create claim. Please try again.")

    return _to_detail_out(db, claim)


@router.get("", response_model=List[ClaimOut])
def list_claims(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Customer: own claims. Admin/support: all claims (with optional status filter)."""
    if current_user.role.name in ("admin", "support"):
        q = db.query(Claim)
    else:
        cust = _get_customer(db, current_user)
        q = db.query(Claim).filter(Claim.customer_id == cust.id)

    if status_filter:
        if status_filter not in {"SUBMITTED","PROCESSING","UNDER_REVIEW","APPROVED","REJECTED","MORE_INFORMATION_REQUIRED","RESOLVED"}:
            raise HTTPException(status_code=422, detail="Invalid status filter.")
        q = q.filter(Claim.status == status_filter)

    claims = q.order_by(Claim.created_at.desc()).all()
    return [_to_claim_out(c) for c in claims]


@router.get("/{claim_id}", response_model=ClaimDetailOut)
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_404(db, claim_id)
    _verify_claim_access(claim, current_user, db)
    return _to_detail_out(db, claim)


@router.post("/{claim_id}/evidence", response_model=EvidenceOut, status_code=201)
def upload_evidence(
    claim_id: int,
    file: UploadFile = File(...),
    evidence_type: str = Form("OTHER"),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Secure file upload. Validates ownership, file type/size, stores file, creates evidence + timeline.
    evidence_type: INVOICE | PHOTO | VIDEO | OTHER
    """
    # Normalize evidence_type
    evidence_type = evidence_type.upper().strip()
    if evidence_type not in {"INVOICE", "PHOTO", "VIDEO", "OTHER"}:
        # backward compat: invoice/photo/video lower
        evidence_type = evidence_type.upper()
        if evidence_type not in {"INVOICE", "PHOTO", "VIDEO", "OTHER"}:
            raise HTTPException(status_code=422, detail="Invalid evidence_type. Use INVOICE, PHOTO, VIDEO, OTHER.")

    claim = _get_claim_or_404(db, claim_id)
    _verify_claim_access(claim, current_user, db)

    # Only customer owner or admin can upload — already verified via _verify_claim_access
    # But ensure claim not in terminal state? Allow upload in any case except RESOLVED/REJECTED? For 1.2 allow all except RESOLVED
    if claim.status == "RESOLVED":
        raise HTTPException(status_code=409, detail="Cannot upload evidence to a resolved claim.")

    # Save file securely
    try:
        rel_path, stored, size, mime = save_upload(file, claim_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="File storage failed. Please try again.")

    try:
        evidence = ClaimEvidence(
            claim_id=claim.id,
            evidence_type=evidence_type,
            file_path=rel_path,
            original_filename=file.filename,
            stored_filename=stored,
            mime_type=mime,
            file_size=size,
            uploaded_by_user_id=current_user.id,
            description=description,
        )
        db.add(evidence)
        db.flush()
        # Timeline
        tl = ClaimTimeline(
            claim_id=claim.id,
            event_type="EVIDENCE_UPLOADED",
            actor=f"{current_user.role.name}:{current_user.email}",
            notes=f"{evidence_type} uploaded: {file.filename} ({size} bytes)",
            event_metadata={
                "evidence_id": evidence.id,
                "evidence_type": evidence_type,
                "filename": file.filename,
                "mime": mime,
            },
        )
        db.add(tl)
        # If claim was MORE_INFORMATION_REQUIRED, auto-transition to PROCESSING
        if claim.status == "MORE_INFORMATION_REQUIRED":
            old = claim.status
            claim.status = "PROCESSING"
            tl2 = ClaimTimeline(
                claim_id=claim.id,
                event_type="STATUS_CHANGED",
                actor="system",
                notes=f"Status {old} -> PROCESSING (evidence provided)",
                event_metadata={"from": old, "to": "PROCESSING", "reason": "evidence uploaded"},
            )
            db.add(tl2)

        db.commit()
        db.refresh(evidence)
    except Exception:
        db.rollback()
        # cleanup file
        try:
            delete_file(rel_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save evidence. Please try again.")

    return EvidenceOut.model_validate(evidence)


@router.get("/{claim_id}/evidence", response_model=List[EvidenceOut])
def list_evidence(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_404(db, claim_id)
    _verify_claim_access(claim, current_user, db)
    ev = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).order_by(ClaimEvidence.uploaded_at.desc()).all()
    return [EvidenceOut.model_validate(e) for e in ev]


@router.get("/{claim_id}/timeline", response_model=List[TimelineEventOut])
def list_timeline(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_404(db, claim_id)
    _verify_claim_access(claim, current_user, db)
    tl = db.query(ClaimTimeline).filter(ClaimTimeline.claim_id == claim.id).order_by(ClaimTimeline.created_at.asc()).all()
    return [TimelineEventOut.model_validate(t) for t in tl]


@router.patch("/{claim_id}/status", response_model=ClaimOut)
def update_status(
    claim_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Centralized status transition. Customers limited to MORE_INFORMATION_REQUIRED->PROCESSING, admins can do all valid.
    """
    claim = _get_claim_or_404(db, claim_id)
    _verify_claim_access(claim, current_user, db)

    new_status = payload.new_status.upper().strip()
    # Role-based restrictions
    if current_user.role.name == "customer":
        # Customer only allowed to move from MORE_INFORMATION_REQUIRED to PROCESSING
        if not (claim.status == "MORE_INFORMATION_REQUIRED" and new_status == "PROCESSING"):
            raise HTTPException(status_code=403, detail="Customers can only move claims from MORE_INFORMATION_REQUIRED to PROCESSING.")
    # Admin/support can do any valid transition — but still must be valid per machine

    assert_valid_transition(claim.status, new_status)
    old = claim.status
    try:
        claim.status = new_status
        tl = ClaimTimeline(
            claim_id=claim.id,
            event_type="STATUS_CHANGED",
            actor=f"{current_user.role.name}:{current_user.email}",
            notes=payload.notes or f"Status {old} -> {new_status}",
            event_metadata={"from": old, "to": new_status, "notes": payload.notes},
        )
        db.add(tl)
        db.commit()
        db.refresh(claim)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update status.")

    return _to_claim_out(claim)

