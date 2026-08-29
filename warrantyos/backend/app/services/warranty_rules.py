"""
WarrantyRuleEngine — deterministic, no AI.

Evaluates warranty eligibility based on product, serial ownership, purchase date,
warranty policy, and fault information. Used at claim creation and exposed to admin
claim detail.

Design for Part 2: returns structured dict that AI layer can enrich later, but
engine itself never calls RocketRide.
"""

from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Optional, List

from app.models.product import Product, ProductSerial, WarrantyPolicy


@dataclass
class WarrantyResult:
    eligible: bool
    warranty_active: bool
    policy_match: bool
    reason: str
    exclusions_triggered: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    # detailed fields for claim persistence
    purchase_date: Optional[date] = None
    warranty_end_date: Optional[date] = None
    days_since_purchase: Optional[int] = None


def _add_months(src: date, months: int) -> date:
    """Add months to date, handling year rollover and month-end."""
    year = src.year + (src.month - 1 + months) // 12
    month = (src.month - 1 + months) % 12 + 1
    # clamp day to last day of target month
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day = min(src.day, last_day)
    return date(year, month, day)


def evaluate_warranty(
    *,
    product: Optional[Product],
    serial: Optional[ProductSerial],
    policy: Optional[WarrantyPolicy],
    customer_id: Optional[int],
    fault_description: Optional[str],
    fault_category: Optional[str],
    purchase_date_override: Optional[date] = None,
    today: Optional[date] = None,
) -> WarrantyResult:
    """
    Deterministic eligibility evaluation.

    Rules:
    1. Product exists
    2. Serial exists (if provided)
    3. Ownership matches (if serial has owner)
    4. Purchase date valid
    5. Policy exists
    6. Warranty period not expired
    7. Required info present
    8. Exclusions respected
    """
    today = today or date.today()
    missing = []
    exclusions = []

    # 1. Product exists
    if not product:
        return WarrantyResult(
            eligible=False,
            warranty_active=False,
            policy_match=False,
            reason="INVALID_PRODUCT: Product does not exist.",
            missing_information=missing,
            exclusions_triggered=exclusions,
        )

    # 7. Required info
    if not fault_description or not fault_description.strip():
        missing.append("Fault description is required.")
    if not fault_description or len(fault_description.strip()) < 10:
        missing.append("Fault description too short; provide details.")

    # Determine purchase date
    purchase_date = purchase_date_override
    if not purchase_date and serial:
        purchase_date = serial.purchase_date
    # if serial exists but no purchase_date, treat as missing
    if serial and not purchase_date:
        missing.append("Purchase date not found for this serial.")

    # 2. Serial existence — if caller provided serial_number that didn't resolve, `serial` will be None
    # Caller should distinguish "invalid serial" vs "no serial provided". We treat None serial as "no serial"
    # but if product requires serial, it's not strictly required in 1.2; we just check ownership if serial present.

    # 3. Ownership
    if serial and serial.owner_customer_id is not None and customer_id is not None:
        if serial.owner_customer_id != customer_id:
            return WarrantyResult(
                eligible=False,
                warranty_active=False,
                policy_match=False,
                reason="OWNERSHIP_MISMATCH: Product serial is not owned by this customer.",
                missing_information=missing,
                exclusions_triggered=exclusions,
                purchase_date=purchase_date,
            )

    # 4. Purchase date valid
    if purchase_date and purchase_date > today:
        return WarrantyResult(
            eligible=False,
            warranty_active=False,
            policy_match=False,
            reason="INVALID_PURCHASE_DATE: Purchase date is in the future.",
            missing_information=missing,
            exclusions_triggered=exclusions,
            purchase_date=purchase_date,
        )

    # 5. Policy exists
    if not policy:
        return WarrantyResult(
            eligible=False,
            warranty_active=False,
            policy_match=False,
            reason="MISSING_POLICY: No warranty policy found for this product.",
            missing_information=missing,
            exclusions_triggered=exclusions,
            purchase_date=purchase_date,
        )

    # Calculate warranty window
    warranty_months = policy.warranty_months or product.warranty_period_months or 12
    warranty_end = None
    days_since = None
    warranty_active = False
    if purchase_date:
        warranty_end = _add_months(purchase_date, warranty_months)
        days_since = (today - purchase_date).days
        warranty_active = today <= warranty_end
        # 6. Expired check
        if not warranty_active:
            return WarrantyResult(
                eligible=False,
                warranty_active=False,
                policy_match=True,
                reason=f"EXPIRED: Warranty expired on {warranty_end.isoformat()}. Purchased {purchase_date.isoformat()}, {warranty_months} months coverage.",
                missing_information=missing,
                exclusions_triggered=exclusions,
                purchase_date=purchase_date,
                warranty_end_date=warranty_end,
                days_since_purchase=days_since,
            )
    else:
        # No purchase date -> cannot determine active
        if not missing:
            missing.append("Purchase date required to verify warranty.")
        return WarrantyResult(
            eligible=False,
            warranty_active=False,
            policy_match=True,
            reason="MISSING_INFORMATION: Purchase date required to verify warranty.",
            missing_information=missing,
            exclusions_triggered=exclusions,
            purchase_date=purchase_date,
            warranty_end_date=warranty_end,
            days_since_purchase=days_since,
        )

    # 8. Exclusions — check fault_description and fault_category against not_covered
    fault_text = f"{fault_description or ''} {fault_category or ''}".lower()
    if policy.not_covered:
        for excl in policy.not_covered:
            if excl and excl.lower() in fault_text:
                exclusions.append(excl)
    # Also check policy.covered_fault_categories if present — if fault_category is set and not in covered list, mark as not matched?
    # For now, exclusions only; covered is informational.

    if exclusions:
        return WarrantyResult(
            eligible=False,
            warranty_active=True,
            policy_match=False,
            reason=f"EXCLUDED: Claim matches policy exclusion(s): {', '.join(exclusions)}.",
            missing_information=missing,
            exclusions_triggered=exclusions,
            purchase_date=purchase_date,
            warranty_end_date=warranty_end,
            days_since_purchase=days_since,
        )

    if missing:
        return WarrantyResult(
            eligible=False,
            warranty_active=warranty_active,
            policy_match=True,
            reason="MISSING_INFORMATION: Required information missing.",
            missing_information=missing,
            exclusions_triggered=exclusions,
            purchase_date=purchase_date,
            warranty_end_date=warranty_end,
            days_since_purchase=days_since,
        )

    # Valid
    return WarrantyResult(
        eligible=True,
        warranty_active=True,
        policy_match=True,
        reason="VALID: Warranty active, product verified, policy conditions satisfied.",
        missing_information=missing,
        exclusions_triggered=exclusions,
        purchase_date=purchase_date,
        warranty_end_date=warranty_end,
        days_since_purchase=days_since,
    )
