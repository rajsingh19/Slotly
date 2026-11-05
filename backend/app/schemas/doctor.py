from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DoctorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    specialization: str = Field(..., min_length=2, max_length=100)
    availability: str = Field(..., description="JSON-encoded availability schedule or slots")
    consultation_fee: float = Field(50.0, ge=0.0)
    is_active: bool = True


class DoctorCreate(DoctorBase):
    pass


class DoctorOut(DoctorBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AvailabilitySlot(BaseModel):
    time: str
    is_available: bool


class DoctorAvailabilityOut(BaseModel):
    doctor_id: int
    doctor_name: str
    specialization: str
    date: date
    slots: List[AvailabilitySlot]
