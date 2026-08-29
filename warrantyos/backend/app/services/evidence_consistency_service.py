"""
Evidence Consistency Service — Part 2.6
Cross-checks OCR extracted document data against claim, product, serial, and purchase date.
Generates structured risk signals for inconsistency detection.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimEvidence
from app.models.product import Product, ProductSerial, Retailer
from app.schemas.evidence_ai import ExtractedDocument, RiskSignal


def check_evidence_consistency(
    db: Session,
    claim: Claim,
    extracted_doc: Optional[ExtractedDocument] = None
) -> List[RiskSignal]:
    """
    Cross-references extracted invoice/document data against claim database records.
    Returns structured RiskSignals for any discrepancies found.
    """
    signals: List[RiskSignal] = []

    if not extracted_doc or extracted_doc.extraction_confidence < 0.2:
        return signals

    # Load claim relational data
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
    retailer = db.query(Retailer).filter(Retailer.id == claim.retailer_id).first() if claim.retailer_id else None

    # 1. SERIAL_MISMATCH
    if extracted_doc.serial_number and serial:
        extracted_sn = extracted_doc.serial_number.strip().upper()
        record_sn = serial.serial_number.strip().upper()
        if extracted_sn != record_sn:
            signals.append(RiskSignal(
                code="SERIAL_MISMATCH",
                severity="HIGH",
                description=f"OCR extracted serial '{extracted_sn}' does not match registered serial '{record_sn}'",
                source="OCR_CONSISTENCY",
                confidence=0.94,
                metadata={"extracted": extracted_sn, "registered": record_sn}
            ))

    # 2. PRODUCT_MISMATCH
    if extracted_doc.product_name and product:
        ext_p = extracted_doc.product_name.strip().lower()
        rec_p = product.name.strip().lower()
        # Check token intersection or substring match
        if ext_p not in rec_p and rec_p not in ext_p:
            ext_tokens = set(ext_p.split())
            rec_tokens = set(rec_p.split())
            if not (ext_tokens & rec_tokens):
                signals.append(RiskSignal(
                    code="PRODUCT_MISMATCH",
                    severity="HIGH",
                    description=f"OCR invoice product '{extracted_doc.product_name}' mismatches registered product '{product.name}'",
                    source="OCR_CONSISTENCY",
                    confidence=0.91,
                    metadata={"extracted": extracted_doc.product_name, "registered": product.name}
                ))

    # 3. PURCHASE_DATE_MISMATCH
    if extracted_doc.purchase_date:
        claim_pur = claim.purchase_date or (serial.purchase_date if serial else None)
        if claim_pur:
            if isinstance(claim_pur, str):
                try:
                    claim_pur = date.fromisoformat(claim_pur)
                except Exception:
                    claim_pur = None
            if claim_pur and extracted_doc.purchase_date != claim_pur:
                diff_days = abs((extracted_doc.purchase_date - claim_pur).days)
                if diff_days > 7:
                    signals.append(RiskSignal(
                        code="PURCHASE_DATE_MISMATCH",
                        severity="MEDIUM" if diff_days < 30 else "HIGH",
                        description=f"OCR invoice date ({extracted_doc.purchase_date}) differs from claim purchase date ({claim_pur}) by {diff_days} days",
                        source="OCR_CONSISTENCY",
                        confidence=0.89,
                        metadata={"extracted": str(extracted_doc.purchase_date), "claim_date": str(claim_pur), "diff_days": diff_days}
                    ))

    # 4. SELLER_MISMATCH
    if extracted_doc.seller and retailer:
        ext_s = extracted_doc.seller.strip().lower()
        rec_s = retailer.name.strip().lower()
        if ext_s not in rec_s and rec_s not in ext_s:
            signals.append(RiskSignal(
                code="SELLER_MISMATCH",
                severity="MEDIUM",
                description=f"OCR seller '{extracted_doc.seller}' does not match retailer '{retailer.name}'",
                source="OCR_CONSISTENCY",
                confidence=0.82,
                metadata={"extracted": extracted_doc.seller, "registered": retailer.name}
            ))

    # 5. AMOUNT_ANOMALY
    if extracted_doc.amount is not None:
        if extracted_doc.amount <= 0 or extracted_doc.amount > 10000:
            signals.append(RiskSignal(
                code="AMOUNT_ANOMALY",
                severity="MEDIUM" if extracted_doc.amount > 0 else "HIGH",
                description=f"Extracted invoice amount ${extracted_doc.amount:.2f} flagged as potential anomaly",
                source="OCR_CONSISTENCY",
                confidence=0.85,
                metadata={"amount": extracted_doc.amount}
            ))

    # 6. DUPLICATE_INVOICE
    if extracted_doc.invoice_number:
        other_claims_count = 0
        try:
            all_evs = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id != claim.id).all()
            for ev in all_evs:
                if ev.description and extracted_doc.invoice_number in ev.description:
                    other_claims_count += 1
        except Exception:
            pass

        if other_claims_count > 0:
            signals.append(RiskSignal(
                code="DUPLICATE_INVOICE",
                severity="HIGH",
                description=f"Invoice number '{extracted_doc.invoice_number}' associated with {other_claims_count} other claim(s)",
                source="OCR_CONSISTENCY",
                confidence=0.95,
                metadata={"invoice_number": extracted_doc.invoice_number, "other_claims_count": other_claims_count}
            ))

    return signals
