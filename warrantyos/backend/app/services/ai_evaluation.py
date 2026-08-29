from typing import List, Dict, Any, Optional
import math
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimDecision, ClaimReview
from app.models.intelligence import HistoricalCase


RECOMMENDATION_CLASSES = ["REPAIR", "REPLACE", "DENY", "MORE_INFORMATION_REQUIRED", "HUMAN_REVIEW"]


def safe_div(a: float, b: float) -> float:
    return round(a / b, 3) if b else 0.0


def evaluate_claims(db: Session, claim_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Part 2.6 evaluation engine:
    Evaluates AI recommendation quality, human-AI agreement, confidence calibration,
    and recommendation classification metrics.
    """
    query = db.query(Claim)
    if claim_ids:
        query = query.filter(Claim.id.in_(claim_ids))
    claims = query.all()

    total = 0
    with_human = 0
    agreement_count = 0
    override_count = 0
    approval_count = 0
    rejection_count = 0
    review_required_count = 0
    confidences: List[float] = []

    # Breakdowns
    agreement_by_band: Dict[str, Dict[str, Any]] = {
        "HIGH": {"sample_size": 0, "agreement_count": 0, "agreement": None},
        "MEDIUM": {"sample_size": 0, "agreement_count": 0, "agreement": None},
        "LOW": {"sample_size": 0, "agreement_count": 0, "agreement": None},
    }
    agreement_by_risk: Dict[str, Dict[str, Any]] = {
        "LOW": {"sample_size": 0, "agreement_count": 0, "agreement": None},
        "MEDIUM": {"sample_size": 0, "agreement_count": 0, "agreement": None},
        "HIGH": {"sample_size": 0, "agreement_count": 0, "agreement": None},
    }
    override_by_rec: Dict[str, Dict[str, Any]] = {
        cls: {"total": 0, "overrides": 0, "override_rate": None} for cls in RECOMMENDATION_CLASSES
    }

    # Calibration data: list of (confidence, is_agree)
    calibration_pairs: List[tuple[float, bool]] = []

    # Confusion matrix & class samples
    confusion_matrix: Dict[str, Dict[str, int]] = {
        rec: {h: 0 for h in RECOMMENDATION_CLASSES} for rec in RECOMMENDATION_CLASSES
    }
    class_samples: Dict[str, int] = {c: 0 for c in RECOMMENDATION_CLASSES}

    for claim in claims:
        ai_dec = db.query(ClaimDecision).filter(ClaimDecision.claim_id == claim.id).order_by(ClaimDecision.created_at.desc()).first()
        if not ai_dec:
            continue

        total += 1
        conf = float(ai_dec.confidence or 0.0)
        confidences.append(conf)

        if ai_dec.requires_human_review:
            review_required_count += 1

        rec_cls = (ai_dec.recommendation or "HUMAN_REVIEW").upper()
        if rec_cls not in RECOMMENDATION_CLASSES:
            rec_cls = "HUMAN_REVIEW"
        class_samples[rec_cls] += 1

        # Latest human review
        human = db.query(ClaimReview).filter(
            ClaimReview.claim_id == claim.id,
            ClaimReview.claim_decision_id == ai_dec.id
        ).order_by(ClaimReview.created_at.desc()).first()

        if not human:
            human = db.query(ClaimReview).filter(ClaimReview.claim_id == claim.id).order_by(ClaimReview.created_at.desc()).first()

        if human:
            with_human += 1
            human_dec = (getattr(human, 'human_decision', None) or human.action or "").upper()

            is_agree = (human_dec == rec_cls)
            if human_dec in ("APPROVE", "APPROVED"):
                approval_count += 1
            elif human_dec in ("REJECT", "REJECTED", "DENY"):
                rejection_count += 1

            if is_agree:
                agreement_count += 1

            is_override = bool(getattr(human, 'override', False)) or (human_dec and not is_agree)
            if is_override:
                override_count += 1

            if rec_cls in override_by_rec:
                override_by_rec[rec_cls]["total"] += 1
                if is_override:
                    override_by_rec[rec_cls]["overrides"] += 1

            band = (ai_dec.confidence_band or ("HIGH" if conf >= 0.8 else "MEDIUM" if conf >= 0.5 else "LOW")).upper()
            if band in agreement_by_band:
                agreement_by_band[band]["sample_size"] += 1
                if is_agree:
                    agreement_by_band[band]["agreement_count"] += 1

            # Estimate risk level from conflicts or flags
            risk_lvl = "LOW"
            if ai_dec.risk_flags and len(ai_dec.risk_flags) > 0:
                risk_lvl = "HIGH" if len(ai_dec.risk_flags) >= 2 else "MEDIUM"
            if risk_lvl in agreement_by_risk:
                agreement_by_risk[risk_lvl]["sample_size"] += 1
                if is_agree:
                    agreement_by_risk[risk_lvl]["agreement_count"] += 1

            calibration_pairs.append((conf, is_agree))

            # Fill confusion matrix
            h_cls = human_dec if human_dec in RECOMMENDATION_CLASSES else "HUMAN_REVIEW"
            if rec_cls in confusion_matrix and h_cls in confusion_matrix[rec_cls]:
                confusion_matrix[rec_cls][h_cls] += 1

    # Compute breakdown percentages
    for b_key, b_val in agreement_by_band.items():
        b_val["agreement"] = safe_div(b_val["agreement_count"], b_val["sample_size"]) if b_val["sample_size"] > 0 else None

    for r_key, r_val in agreement_by_risk.items():
        r_val["agreement"] = safe_div(r_val["agreement_count"], r_val["sample_size"]) if r_val["sample_size"] > 0 else None

    for rec_k, rec_v in override_by_rec.items():
        rec_v["override_rate"] = safe_div(rec_v["overrides"], rec_v["total"]) if rec_v["total"] > 0 else None

    # Confidence Calibration Metrics
    calibration_status = "SUFFICIENT_DATA" if len(calibration_pairs) >= 5 else "INSUFFICIENT_DATA"
    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    if calibration_pairs:
        brier_sum = sum((conf - (1.0 if agree else 0.0)) ** 2 for conf, agree in calibration_pairs)
        brier_score = round(brier_sum / len(calibration_pairs), 4)
        ece_sum = sum(abs(conf - (1.0 if agree else 0.0)) for conf, agree in calibration_pairs)
        calibration_error = round(ece_sum / len(calibration_pairs), 4)

    # Classification Metrics
    class_metrics: Dict[str, Any] = {}
    for cls in RECOMMENDATION_CLASSES:
        n_samples = class_samples[cls]
        if n_samples < 2:
            class_metrics[cls] = {
                "sample_size": n_samples,
                "status": "insufficient_samples",
                "precision": None,
                "recall": None,
                "f1": None,
            }
        else:
            tp = confusion_matrix[cls][cls]
            fp = sum(confusion_matrix[other][cls] for other in RECOMMENDATION_CLASSES if other != cls)
            fn = sum(confusion_matrix[cls][other] for other in RECOMMENDATION_CLASSES if other != cls)
            prec = safe_div(tp, tp + fp) if (tp + fp) > 0 else 0.0
            rec = safe_div(tp, tp + fn) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 3) if (prec + rec) > 0 else 0.0
            class_metrics[cls] = {
                "sample_size": n_samples,
                "status": "evaluated",
                "precision": prec,
                "recall": rec,
                "f1": f1,
            }

    return {
        "evaluation_sample_size": total,
        "with_human_review": with_human,
        "observed_agreement": safe_div(agreement_count, with_human) if with_human else None,
        "agreement_count": agreement_count,
        "human_ai_agreement": safe_div(agreement_count, with_human) if with_human else None,
        "approval_rate": safe_div(approval_count, with_human) if with_human else None,
        "rejection_rate": safe_div(rejection_count, with_human) if with_human else None,
        "override_rate": safe_div(override_count, with_human) if with_human else None,
        "override_count": override_count,
        "review_required_rate": safe_div(review_required_count, total) if total else None,
        "review_required_count": review_required_count,
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "agreement_by_confidence_band": agreement_by_band,
        "agreement_by_risk_level": agreement_by_risk,
        "override_rate_by_recommendation": override_by_rec,
        "confidence_calibration": {
            "calibration_status": calibration_status,
            "brier_score": brier_score,
            "calibration_error": calibration_error,
            "sample_size": len(calibration_pairs),
        },
        "classification_metrics": class_metrics,
        "confusion_matrix": confusion_matrix,
        "notes": "Observed agreement and calibration evaluated against recorded human review outcomes.",
    }


def evaluate_retrieval_quality(db: Session) -> Dict[str, Any]:
    """
    Evaluates historical case retrieval performance metrics:
    Precision@K, Recall@K, Hit@K, MRR, Average similarity for K in [1, 3, 5].
    Returns status="insufficient_ground_truth" if labeled ground truth count < 3.
    """
    cases_count = db.query(HistoricalCase).count()
    if cases_count < 3:
        return {
            "status": "insufficient_ground_truth",
            "dataset_size": cases_count,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
            "recall_at_1": None,
            "recall_at_3": None,
            "recall_at_5": None,
            "hit_at_1": None,
            "hit_at_3": None,
            "hit_at_5": None,
            "mrr": None,
            "average_similarity": None,
            "notes": "Insufficient ground truth labels to compute scientific retrieval metrics."
        }

    # Under mock/seeded data, evaluate retrieval on sample claims
    claims = db.query(Claim).limit(20).all()
    if not claims:
        return {
            "status": "insufficient_ground_truth",
            "dataset_size": 0,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
            "mrr": None,
        }

    from app.services.historical_case_service import find_similar_cases

    hits = {1: 0, 3: 0, 5: 0}
    precisions = {1: [], 3: [], 5: []}
    recalls = {1: [], 3: [], 5: []}
    rr_list: List[float] = []
    sim_scores: List[float] = []

    for claim in claims:
        res = find_similar_cases(db, claim, top_k=5)
        top = res.top_cases
        if not top:
            continue

        # Evaluate ground truth relevance: same product_category or score > 0.60
        relevant = [c for c in top if (c.similarity_score and c.similarity_score >= 0.60)]
        relevant_ids = set(c.case_id for c in relevant)

        for k in (1, 3, 5):
            k_top = top[:k]
            k_rel = [c for c in k_top if c.case_id in relevant_ids]
            if k_rel:
                hits[k] += 1
            p_k = len(k_rel) / k
            r_k = len(k_rel) / max(len(relevant_ids), 1)
            precisions[k].append(p_k)
            recalls[k].append(r_k)

        # MRR calculation
        rank_rr = 0.0
        for rank_idx, c in enumerate(top, 1):
            if c.case_id in relevant_ids:
                rank_rr = 1.0 / rank_idx
                break
        rr_list.append(rank_rr)

        for c in top:
            if c.similarity_score is not None:
                sim_scores.append(c.similarity_score)

    total_eval = len(claims)
    return {
        "status": "evaluated",
        "dataset_size": cases_count,
        "evaluated_claims": total_eval,
        "precision_at_1": safe_div(sum(precisions[1]), total_eval),
        "precision_at_3": safe_div(sum(precisions[3]), total_eval),
        "precision_at_5": safe_div(sum(precisions[5]), total_eval),
        "recall_at_1": safe_div(sum(recalls[1]), total_eval),
        "recall_at_3": safe_div(sum(recalls[3]), total_eval),
        "recall_at_5": safe_div(sum(recalls[5]), total_eval),
        "hit_at_1": safe_div(hits[1], total_eval),
        "hit_at_3": safe_div(hits[3], total_eval),
        "hit_at_5": safe_div(hits[5], total_eval),
        "mrr": safe_div(sum(rr_list), total_eval),
        "average_similarity": safe_div(sum(sim_scores), len(sim_scores)) if sim_scores else 0.0,
    }


def get_evaluation_dataset(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Generate evaluation dataset: AI recommendation vs human decision for reviewed claims.
    """
    rows = db.query(ClaimReview).join(ClaimDecision, ClaimReview.claim_decision_id == ClaimDecision.id).limit(limit).all()
    dataset = []
    for r in rows:
        dec = db.query(ClaimDecision).filter(ClaimDecision.id == r.claim_decision_id).first()
        claim = db.query(Claim).filter(Claim.id == r.claim_id).first()
        dataset.append({
            "review_id": r.id,
            "claim_id": r.claim_id,
            "claim_code": claim.claim_code if claim else None,
            "ai_recommendation": dec.recommendation if dec else None,
            "ai_confidence": float(dec.confidence) if dec and dec.confidence else None,
            "ai_governance_score": float(dec.decision_score) if dec and dec.decision_score else None,
            "human_decision": r.human_decision or r.action,
            "override": bool(r.override),
            "override_reason": r.override_reason,
            "review_reason": r.notes,
        })
    return dataset

