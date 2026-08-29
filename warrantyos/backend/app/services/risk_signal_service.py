"""
Risk Signal Engine — Part 2.2
Deterministic risk signals from claim data. No "fraud" labels, only risk indicators.
"""

from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimEvidence
from app.models.product import ProductSerial, WarrantyPolicy, Product
from app.schemas.evidence_ai import RiskSignal, NormalizedEvidence


def generate_risk_signals(db: Session, claim: Claim, normalized: NormalizedEvidence) -> List[RiskSignal]:
    signals: List[RiskSignal] = []

    # Helper to add signal
    def add(code, severity, desc, source, conf, meta=None):
        signals.append(RiskSignal(
            code=code,
            severity=severity,
            description=desc,
            source=source,
            confidence=conf,
            metadata=meta or {}
        ))

    # 1. MULTIPLE_RECENT_CLAIMS (90 days)
    since = datetime.now(timezone.utc) - timedelta(days=90)
    try:
        count_90d = db.query(Claim).filter(Claim.customer_id == claim.customer_id, Claim.created_at >= since).count()
    except Exception:
        count_90d = 0
    if count_90d >= 3:
        add(
            "MULTIPLE_RECENT_CLAIMS",
            "MEDIUM" if count_90d < 5 else "HIGH",
            f"Customer has {count_90d} claims within the previous 90 days.",
            "claim_history",
            1.0,
            {"count": count_90d}
        )

    # 2. MISSING_INVOICE
    has_invoice = any(item.evidence_type == "invoice" and item.present for item in normalized.items)
    if not has_invoice:
        add("MISSING_INVOICE", "MEDIUM", "Invoice not provided. Proof of purchase is required per policy.", "evidence", 1.0)

    # 3. MISSING_PRODUCT_PHOTO
    has_photo = any(item.evidence_type == "photo" and item.present for item in normalized.items)
    if not has_photo:
        add("MISSING_PRODUCT_PHOTO", "MEDIUM", "Product photo not provided. Visual evidence is required.", "evidence", 1.0)

    # 4. SERIAL_MISMATCH
    if claim.serial_id:
        serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first()
        if serial and serial.product_id != claim.product_id:
            add("SERIAL_MISMATCH", "HIGH", "Serial number does not belong to the selected product.", "claim", 1.0)

    # 5. EXPIRED_WARRANTY
    if claim.warranty_eligible is False and claim.eligibility_reason and "EXPIRED" in claim.eligibility_reason:
        add("EXPIRED_WARRANTY", "HIGH", f"Warranty expired: {claim.eligibility_reason}", "warranty", 1.0)

    # 6. ACCIDENTAL_DAMAGE_PATTERN
    fault_low = (claim.fault_description or "").lower()
    if any(kw in fault_low for kw in ["physical damage", "accidental", "drop", "cracked", "dent"]):
        add("ACCIDENTAL_DAMAGE_PATTERN", "MEDIUM", "Fault description matches accidental/physical damage pattern. Requires policy exclusion check.", "fault_description", 0.85)

    # 7. UNAUTHORIZED_REPAIR_PATTERN
    if any(kw in fault_low for kw in ["unauthorized", "repair attempt", "opened", "tampered"]):
        add("UNAUTHORIZED_REPAIR_PATTERN", "MEDIUM", "Possible unauthorized repair attempt mentioned.", "fault_description", 0.8)

    # 8. INCONSISTENT_PURCHASE_DATE
    if claim.purchase_date:
        try:
            # If purchase_date is string from claim, parse; else date
            from datetime import date
            pur = claim.purchase_date
            if isinstance(pur, str):
                pur = date.fromisoformat(pur)
            if pur and pur > date.today():
                add("INCONSISTENT_PURCHASE_DATE", "HIGH", "Purchase date is in the future.", "claim", 1.0)
        except Exception:
            pass

    # 9. INCONSISTENT_PRODUCT_INFORMATION
    # Check if fault_category not in policy covered_fault_categories
    if claim.fault_category:
        product = db.query(Product).filter(Product.id == claim.product_id).first()
        policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == claim.product_id).first() if product else None
        if policy and policy.covered_fault_categories:
            if claim.fault_category not in [c.lower() for c in policy.covered_fault_categories]:
                # Not necessarily risk, but potential inconsistency
                pass  # don't add for now to avoid noise

    # 10. INSUFFICIENT_EVIDENCE
    if normalized.completeness.overall == "INCOMPLETE":
        add("INSUFFICIENT_EVIDENCE", "MEDIUM", f"Evidence incomplete: missing {', '.join(normalized.completeness.missing)}", "evidence", 0.9, {"missing": normalized.completeness.missing})
    elif normalized.completeness.overall == "PARTIAL":
        add("INSUFFICIENT_EVIDENCE", "LOW", f"Evidence partially complete, missing {', '.join(normalized.completeness.missing)}", "evidence", 0.6)

    # 11. OCR Evidence Consistency Signals (Part 2.6)
    if normalized and normalized.extracted_document:
        from app.services.evidence_consistency_service import check_evidence_consistency
        ocr_signals = check_evidence_consistency(db, claim, normalized.extracted_document)
        signals.extend(ocr_signals)

    return signals

