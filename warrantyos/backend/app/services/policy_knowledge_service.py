"""
Policy Knowledge Base — Part 2.2
Structured retrieval of warranty-policy information for AI context.
Reuses WarrantyPolicy, does not duplicate WarrantyRuleEngine.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.product import WarrantyPolicy, Product
from app.models.claim import Claim
from app.schemas.evidence_ai import PolicyKnowledgeItem


# Knowledge base is derived from WarrantyPolicy.covered/not_covered/conditions
# We expand each policy into discrete knowledge items for retrieval

def _policy_to_knowledge_items(policy: WarrantyPolicy, product: Product) -> List[PolicyKnowledgeItem]:
    items: List[PolicyKnowledgeItem] = []
    base_id = policy.id

    # Coverage items
    if policy.covered:
        for idx, cov in enumerate(policy.covered):
            items.append(PolicyKnowledgeItem(
                policy_id=base_id * 10 + idx,
                product_id=policy.product_id,
                title=f"Coverage: {cov}",
                category="coverage",
                content=cov,
                relevance=0.0,  # to be scored per claim
                reason=""
            ))
    # Non-coverage
    if policy.not_covered:
        for idx, nc in enumerate(policy.not_covered):
            items.append(PolicyKnowledgeItem(
                policy_id=base_id * 100 + idx,
                product_id=policy.product_id,
                title=f"Exclusion: {nc}",
                category="non_coverage",
                content=nc,
                relevance=0.0,
                reason=""
            ))
    # Conditions
    if policy.conditions:
        items.append(PolicyKnowledgeItem(
            policy_id=base_id * 1000,
            product_id=policy.product_id,
            title="Policy Conditions",
            category="conditions",
            content=policy.conditions,
            relevance=0.0,
            reason=""
        ))
    # Specific categories for retrieval (accidental, liquid, etc.)
    # Map not_covered terms to categories
    category_map = {
        "accidental": "accidental_damage",
        "liquid": "liquid_damage",
        "water": "liquid_damage",
        "physical": "physical_damage",
        "unauthorized": "unauthorized_repair",
        "expired": "expired_warranty",
        "proof": "proof_of_purchase",
        "serial": "serial_number_requirements",
    }
    if policy.not_covered:
        for nc in policy.not_covered:
            low = nc.lower()
            for keyword, cat in category_map.items():
                if keyword in low:
                    # Avoid duplicate
                    if not any(i.category == cat and i.content == nc for i in items):
                        items.append(PolicyKnowledgeItem(
                            policy_id=base_id * 10000 + hash(nc) % 1000,
                            product_id=policy.product_id,
                            title=f"Policy: {cat.replace('_',' ').title()}",
                            category=cat,
                            content=nc,
                            relevance=0.0,
                            reason=""
                        ))
    return items


def retrieve_policy_knowledge(db: Session, claim: Claim, top_k: int = 5) -> List[PolicyKnowledgeItem]:
    """
    Deterministic policy retrieval for a claim.
    Input: claim + fault description + product
    Output: top_k relevant policy items with relevance scores.
    """
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    if not product:
        return []

    policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == product.id).first()
    if not policy:
        return []

    all_items = _policy_to_knowledge_items(policy, product)

    # Score each item against claim
    fault_text = f"{claim.fault_description or ''} {claim.fault_category or ''}".lower()
    scored: List[PolicyKnowledgeItem] = []

    for item in all_items:
        # Simple relevance: if item content keywords appear in fault_text, high relevance
        content_low = item.content.lower()
        # Token overlap
        content_tokens = set(content_low.split())
        fault_tokens = set(fault_text.split())
        overlap = len(content_tokens & fault_tokens) / max(len(content_tokens), 1)

        # Direct substring match for exclusions
        if item.category == "non_coverage" and content_low in fault_text:
            relevance = 0.95
            reason = f"Fault description matches exclusion '{item.content}'"
        elif item.category == "coverage" and content_low in fault_text:
            relevance = 0.85
            reason = f"Fault matches covered term '{item.content}'"
        elif overlap > 0.3:
            relevance = 0.6 + overlap * 0.3
            reason = f"Keyword overlap ({overlap:.2f}) with '{item.content}'"
        else:
            # Generic policy items get lower relevance unless fault is empty
            if item.category == "conditions":
                relevance = 0.4
                reason = "General policy conditions"
            else:
                relevance = 0.2
                reason = "General policy reference"

        # Boost for specific risk categories
        if "physical" in fault_text and "physical" in content_low:
            relevance = 0.91
            reason = "Fault description matches accidental-damage exclusion"
        if "water" in fault_text and "water" in content_low:
            relevance = 0.91
            reason = "Fault matches liquid-damage exclusion"

        item.relevance = round(min(relevance, 1.0), 2)
        item.reason = reason
        scored.append(item)

    # Sort by relevance desc, deterministic tie-break by policy_id
    scored.sort(key=lambda x: (-x.relevance, x.policy_id))
    return scored[:top_k]


from abc import ABC, abstractmethod


class PolicyRetriever(ABC):
    @abstractmethod
    def retrieve(self, db: Session, claim: Claim, top_k: int = 5) -> List[PolicyKnowledgeItem]:
        """Retrieve relevant policy items with matched_terms and traceability reason."""
        ...


class KeywordPolicyRetriever(PolicyRetriever):
    def retrieve(self, db: Session, claim: Claim, top_k: int = 5) -> List[PolicyKnowledgeItem]:
        return retrieve_policy_knowledge(db, claim, top_k=top_k)


class VectorPolicyRetriever(PolicyRetriever):
    def retrieve(self, db: Session, claim: Claim, top_k: int = 5) -> List[PolicyKnowledgeItem]:
        # For Part 2.6, falls back to keyword retrieval to remain offline and deterministic
        return retrieve_policy_knowledge(db, claim, top_k=top_k)


def get_policy_retriever() -> PolicyRetriever:
    return KeywordPolicyRetriever()


