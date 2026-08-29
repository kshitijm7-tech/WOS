"""
AI Execution Context — Part 2.4
Structured execution metadata, safe identifiers only.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class AIExecutionContext(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_id: int
    claim_code: str
    provider: str = "mock"
    model: str = "mock-v1"
    pipeline_version: str = "2.4"
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt: int = 1
    timeout_seconds: int = 30
    status: Literal["QUEUED","RUNNING","VALIDATING","GOVERNING","COMPLETED","FAILED","CANCELLED","TIMED_OUT"] = "QUEUED"

    class Config:
        from_attributes = True


class AIExecutionOut(BaseModel):
    id: int
    execution_id: str
    claim_id: int
    status: str
    provider: str
    model: str
    pipeline_version: str
    attempt: int
    requested_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
