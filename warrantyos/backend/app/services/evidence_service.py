"""
Evidence Intelligence Service — Part 2.2
Collects and normalizes all evidence for a claim.
Offline, deterministic, no external calls.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimEvidence
from app.models.product import ProductSerial
from app.schemas.evidence_ai import EvidenceItem, NormalizedEvidence, EvidenceCompleteness, EvidenceCompletenessItem


# What is required vs optional for a warranty claim
REQUIRED_EVIDENCE = {
    "invoice": True,
    "photo": True,
    "serial": True,
    "purchase_date": True,
    "fault_description": True,
}

OPTIONAL_EVIDENCE = {
    "video": False,
    "document": False,
}


def _quality_for(present: bool, required: bool) -> str:
    if present:
        return "AVAILABLE"
    if required:
        return "MISSING"
    return "OPTIONAL"


def collect_evidence(db: Session, claim: Claim) -> List[EvidenceItem]:
    """
    Inspect Claim + ClaimEvidence + ProductSerial and produce normalized list.
    Never exposes file paths.
    """
    evidences = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None

    # Map evidence_type -> presence
    has_invoice = any(e.evidence_type == "INVOICE" for e in evidences)
    has_photo = any(e.evidence_type == "PHOTO" for e in evidences)
    has_video = any(e.evidence_type == "VIDEO" for e in evidences)
    has_document = any(e.evidence_type == "DOCUMENT" for e in evidences)

    items: List[EvidenceItem] = []

    # Invoice
    invoice_files = [e for e in evidences if e.evidence_type == "INVOICE"]
    items.append(EvidenceItem(
        evidence_type="invoice",
        present=has_invoice,
        quality=_quality_for(has_invoice, REQUIRED_EVIDENCE["invoice"]),
        confidence=1.0 if has_invoice else 0.0,
        source="claim_evidence",
        metadata={
            "count": len(invoice_files),
            "mime_types": list({e.mime_type for e in invoice_files if e.mime_type}),
        } if has_invoice else {}
    ))

    # Photo
    photo_files = [e for e in evidences if e.evidence_type == "PHOTO"]
    items.append(EvidenceItem(
        evidence_type="photo",
        present=has_photo,
        quality=_quality_for(has_photo, REQUIRED_EVIDENCE["photo"]),
        confidence=1.0 if has_photo else 0.0,
        source="claim_evidence",
        metadata={"count": len(photo_files)} if has_photo else {}
    ))

    # Video
    video_files = [e for e in evidences if e.evidence_type == "VIDEO"]
    items.append(EvidenceItem(
        evidence_type="video",
        present=has_video,
        quality=_quality_for(has_video, OPTIONAL_EVIDENCE["video"]),
        confidence=1.0 if has_video else 0.0,
        source="claim_evidence",
        metadata={"count": len(video_files)} if has_video else {}
    ))

    # Serial
    has_serial = serial is not None and bool(serial.serial_number)
    items.append(EvidenceItem(
        evidence_type="serial",
        present=has_serial,
        quality=_quality_for(has_serial, REQUIRED_EVIDENCE["serial"]),
        confidence=1.0 if has_serial else 0.0,
        source="product_serial",
        metadata={"serial_number": serial.serial_number if has_serial else None}
    ))

    # Purchase date
    has_purchase = bool(claim.purchase_date or (serial and serial.purchase_date))
    items.append(EvidenceItem(
        evidence_type="purchase_date",
        present=has_purchase,
        quality=_quality_for(has_purchase, REQUIRED_EVIDENCE["purchase_date"]),
        confidence=1.0 if has_purchase else 0.0,
        source="claim" if claim.purchase_date else "product_serial",
        metadata={"purchase_date": str(claim.purchase_date) if claim.purchase_date else (str(serial.purchase_date) if serial and serial.purchase_date else None)}
    ))

    # Fault description
    has_fault = bool(claim.fault_description and len(claim.fault_description.strip()) >= 10)
    items.append(EvidenceItem(
        evidence_type="fault_description",
        present=has_fault,
        quality=_quality_for(has_fault, REQUIRED_EVIDENCE["fault_description"]),
        confidence=1.0 if has_fault else 0.0,
        source="claim",
        metadata={"length": len(claim.fault_description) if claim.fault_description else 0, "fault_category": claim.fault_category}
    ))

    # Document (generic)
    items.append(EvidenceItem(
        evidence_type="document",
        present=has_document,
        quality=_quality_for(has_document, OPTIONAL_EVIDENCE["document"]),
        confidence=1.0 if has_document else 0.0,
        source="claim_evidence",
        metadata={"count": len([e for e in evidences if e.evidence_type == "DOCUMENT"])}
    ))

    return items


def assess_completeness(items: List[EvidenceItem]) -> EvidenceCompleteness:
    """
    Determine AVAILABLE/MISSING/OPTIONAL/INVALID for each evidence type.
    """
    completeness_items: List[EvidenceCompletenessItem] = []
    missing: List[str] = []
    optional_missing: List[str] = []

    # Define required map for completeness (same as REQUIRED_EVIDENCE but explicit)
    required_map = {
        "invoice": True,
        "photo": True,
        "serial": True,
        "purchase_date": True,
        "fault_description": True,
        "video": False,
        "document": False,
    }

    for it in items:
        required = required_map.get(it.evidence_type, False)
        status = it.quality  # already AVAILABLE/MISSING/OPTIONAL
        # Validate: if present but confidence low, could be INVALID (not used in Part 2.2)
        reason = None
        if it.quality == "MISSING" and required:
            reason = f"{it.evidence_type} is required but not provided"
            missing.append(it.evidence_type)
        elif it.quality == "MISSING" and not required:
            optional_missing.append(it.evidence_type)

        completeness_items.append(EvidenceCompletenessItem(
            evidence_type=it.evidence_type,
            status=status,
            required=required,
            present=it.present,
            reason=reason
        ))

    # Overall completeness
    required_present = sum(1 for i in completeness_items if i.required and i.present)
    required_total = sum(1 for i in completeness_items if i.required)
    if required_present == required_total:
        overall = "COMPLETE"
    elif required_present >= required_total * 0.5:
        overall = "PARTIAL"
    else:
        overall = "INCOMPLETE"

    return EvidenceCompleteness(
        items=completeness_items,
        missing=missing,
        optional_missing=optional_missing,
        overall=overall
    )


def build_normalized_evidence(db: Session, claim: Claim, extracted_document=None) -> NormalizedEvidence:
    items = collect_evidence(db, claim)
    completeness = assess_completeness(items)
    total_present = sum(1 for i in items if i.present)
    total_required = sum(1 for i in completeness.items if i.required)
    return NormalizedEvidence(
        items=items,
        completeness=completeness,
        extracted_document=extracted_document,
        total_present=total_present,
        total_required=total_required
    )
