from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class CallEventOut(BaseModel):
    id: int
    call_session_id: int
    event_type: str
    event_data: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CallSessionCreate(BaseModel):
    caller_number: str
    call_direction: str = "INBOUND"
    transcript: Optional[str] = None
    status: str = "COMPLETED"
    estimated_cost: float = 0.0


class CallSessionOut(BaseModel):
    id: int
    caller_number: str
    call_direction: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: int
    transcript: Optional[str] = None
    status: str
    estimated_cost: float

    model_config = ConfigDict(from_attributes=True)


class CallSessionDetailOut(CallSessionOut):
    events: List[CallEventOut] = []
