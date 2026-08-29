"""
Importing every model module here ensures they're all registered on Base.metadata,
so Base.metadata.create_all(engine) (called from main.py on startup) creates every table.
"""

from app.models.user import Role, User, Customer, Admin           # noqa: F401
from app.models.product import (                                   # noqa: F401
    Retailer, Product, ProductionBatch, ProductSerial, WarrantyPolicy,
)
from app.models.claim import (                                     # noqa: F401
    Claim, ClaimEvidence, ClaimAnalysis, ClaimDecision, ClaimReview, ClaimTimeline, AIExecution,
)
from app.models.operations import RepairOrder, Inventory, ReplacementOrder  # noqa: F401
from app.models.intelligence import (                              # noqa: F401
    Notification, HistoricalCase, FaultEvent, RiskFlag, AuditLog,
)
