"""
Evaluation API — Part 2.5
Human feedback loop and model evaluation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.services.ai_evaluation import evaluate_claims, get_evaluation_dataset, evaluate_retrieval_quality

router = APIRouter(prefix="/api/admin/evaluation", tags=["evaluation"])

@router.get("")
def get_evaluation(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin", "support"))):
    result = evaluate_claims(db)
    return result

@router.get("/dataset")
def get_dataset(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin", "support"))):
    dataset = get_evaluation_dataset(db, limit=100)
    return {"dataset": dataset, "count": len(dataset)}

@router.get("/retrieval")
def get_retrieval_evaluation(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin", "support"))):
    return evaluate_retrieval_quality(db)

