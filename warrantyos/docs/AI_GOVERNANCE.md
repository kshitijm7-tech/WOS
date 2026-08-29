# AI Decision Governance — WarrantyOS Part 2.6

## Overview

AI in WarrantyOS is strictly advisory. Final claim determinations remain governed by deterministic rules and human review.

## Governing Principles

1. **Warranty Engine Primacy**:
   ```
   claim.warranty_eligible
   claim.eligibility_reason
   claim.warranty_checked_at
   ```
   Are evaluated exclusively by `WarrantyRuleEngine`. AI cannot mutate or override these fields.

2. **Immutable AI Decisions**:
   Each analysis creates a new versioned `ClaimDecision` row (`decision_version = 1, 2, 3...`). Previous decisions remain auditable in historical records.

3. **Human Review Triggers**:
   A claim is automatically routed to the Human Review queue if:
   - Claim warranty is ineligible or expired (`WARRANTY_CONFLICT`)
   - High severity risk flags are present (`SERIAL_MISMATCH`, `MULTIPLE_RECENT_CLAIMS`)
   - AI confidence is below threshold (`LOW` confidence band)
   - Discrepancy detected in evidence consistency checks

4. **No Chain-of-Thought Storage**:
   Explanations are derived strictly from observable factors (`reasoning_factors`, `supporting`, `contradicting`, `policy_factors`, `historical_factors`, `risk_factors`).
