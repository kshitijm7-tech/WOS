"""
Offline Document Extraction Abstraction — Part 2.2
MockDocumentExtractor simulates extraction from structured claim/evidence metadata.
Architecture allows Real OCR to be plugged in later.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimEvidence
from app.models.product import Product, ProductSerial
from app.schemas.evidence_ai import ExtractedDocument


class DocumentExtractor(ABC):
    @abstractmethod
    def extract(self, db: Session, claim: Claim) -> ExtractedDocument:
        ...


class MockDocumentExtractor(DocumentExtractor):
    """
    Deterministic offline extractor.
    Uses structured claim/evidence metadata as source (no file I/O).
    If actual uploaded files are available and safe local parsing is possible,
    this could read PDFs, but for Part 2.2 we use metadata to stay simple and offline.
    """

    def extract(self, db: Session, claim: Claim) -> ExtractedDocument:
        # Gather base data
        product = db.query(Product).filter(Product.id == claim.product_id).first()
        serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
        evidences = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
        has_invoice = any(e.evidence_type == "INVOICE" for e in evidences)

        # Simulate extraction: if invoice present, we can "extract" fields from claim
        # Otherwise, confidence low and fields None
        if has_invoice:
            # Deterministic pseudo-extraction based on claim data
            invoice_number = f"INV-{claim.claim_code.replace('WR-', '')}"
            purchase_date = claim.purchase_date or (serial.purchase_date if serial else None)
            seller = "Aurelia Direct Store"  # could be derived from retailer, but keep simple
            if claim.retailer_id:
                from app.models.product import Retailer
                retailer = db.query(Retailer).filter(Retailer.id == claim.retailer_id).first()
                if retailer:
                    seller = retailer.name
            product_name = product.name if product else None
            serial_number = serial.serial_number if serial else None
            amount = 299.99  # mock amount, deterministic per claim
            # Simple hash-based variation for amount
            import hashlib
            h = int(hashlib.md5(claim.claim_code.encode()).hexdigest()[:4], 16)
            amount = 100 + (h % 900) + 0.99

            return ExtractedDocument(
                invoice_number=invoice_number,
                purchase_date=purchase_date,
                seller=seller,
                product_name=product_name,
                serial_number=serial_number,
                amount=amount,
                customer_name=None,  # never include PII
                extraction_confidence=0.95,
                source="mock",
                raw_fields={
                    "evidence_count": len(evidences),
                    "has_invoice": True,
                }
            )
        else:
            return ExtractedDocument(
                invoice_number=None,
                purchase_date=claim.purchase_date or (serial.purchase_date if serial else None),
                seller=None,
                product_name=product.name if product else None,
                serial_number=serial.serial_number if serial else None,
                amount=None,
                customer_name=None,
                extraction_confidence=0.35,
                source="mock",
                raw_fields={"has_invoice": False, "reason": "Invoice not provided"}
            )
