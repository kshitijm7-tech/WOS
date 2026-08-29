"""
Deterministic conflict detector — Part 2.3
Detects warranty/AI conflicts, serial mismatches, evidence contradictions.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.product import ProductSerial
from app.schemas.governance import Conflict, ConflictSeverity


def detect_conflicts(db: Session, claim: Claim, ai_recommendation: str) -> List[Conflict]:
    conflicts: List[Conflict] = []

    # 1. Warranty eligible = False but AI says REPAIR/REPLACE
    if claim.warranty_eligible is False and ai_recommendation in ("REPAIR", "REPLACE"):
        conflicts.append(Conflict(
            conflict_code="WARRANTY_CONFLICT",
            description=f"Warranty eligible is False ({claim.eligibility_reason}), but AI recommends {ai_recommendation}.",
            source="warranty",
            severity=ConflictSeverity.HIGH,
            metadata={"warranty_eligible": False, "ai_recommendation": ai_recommendation}
        ))

    # 2. Warranty eligible = True but AI says DENY
    if claim.warranty_eligible is True and ai_recommendation == "DENY":
        conflicts.append(Conflict(
            conflict_code="WARRANTY_CONFLICT",
            description=f"Warranty eligible is True, but AI recommends DENY. Requires human review to ensure denial is justified.",
            source="warranty",
            severity=ConflictSeverity.MEDIUM,
            metadata={"warranty_eligible": True, "ai_recommendation": ai_recommendation}
        ))

    # 3. Serial mismatch (product vs serial)
    if claim.serial_id:
        serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first()
        if serial and serial.product_id != claim.product_id:
            conflicts.append(Conflict(
                conflict_code="SERIAL_MISMATCH",
                description=f"Serial {serial.serial_number} belongs to product {serial.product_id}, but claim is for product {claim.product_id}.",
                source="serial",
                severity=ConflictSeverity.HIGH,
                metadata={"serial_product_id": serial.product_id, "claim_product_id": claim.product_id}
            ))

    # 4. Evidence vs serial product mismatch (if needed, placeholder)
    # Already covered by warranty engine, but we keep explicit

    # 5. Generic: if claim has no evidence but AI recommends REPAIR/REPLACE with high confidence, potential conflict
    # This will be handled via evidence completeness in governance, not here

    return conflicts
