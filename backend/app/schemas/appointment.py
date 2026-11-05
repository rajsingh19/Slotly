import re
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.doctor import DoctorOut
from app.schemas.patient import PatientOut, validate_phone_format


def validate_time_format(v: str) -> str:
    cleaned = v.strip().upper()
    # Support 24-hr HH:MM or 12-hr HH:MM AM/PM
    match_24 = re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", cleaned)
    match_12 = re.match(r"^(0?[1-9]|1[0-2]):[0-5][0-9]\s*(AM|PM)$", cleaned)
    if not (match_24 or match_12):
        raise ValueError("Invalid appointment_time format. Must be HH:MM (e.g. 09:30 or 14:00) or 12-hour (e.g. 09:30 AM).")
    return cleaned


class AppointmentCreate(BaseModel):
    doctor_id: int = Field(..., gt=0, description="Doctor ID")
    appointment_date: date = Field(..., description="Appointment date (YYYY-MM-DD)")
    appointment_time: str = Field(..., description="Time slot, e.g. '10:00' or '10:00 AM'")
    patient_id: Optional[int] = Field(None, gt=0, description="Existing Patient ID")
    patient_name: Optional[str] = Field(None, min_length=2, max_length=100)
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None

    @field_validator("appointment_date")
    @classmethod
    def check_future_date(cls, v: date) -> date:
        if v < date.today():
            raise ValueError(f"Appointment date cannot be in the past ({v} < {date.today()}).")
        return v

    @field_validator("appointment_time")
    @classmethod
    def check_time(cls, v: str) -> str:
        return validate_time_format(v)

    @field_validator("patient_phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return validate_phone_format(v)
        return v

    @model_validator(mode="after")
    def check_patient_identifier(self):
        if not self.patient_id and not (self.patient_name and self.patient_phone):
            raise ValueError("Must provide either 'patient_id' or both 'patient_name' and 'patient_phone'.")
        return self


class AppointmentUpdate(BaseModel):
    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = None
    status: Optional[str] = Field(None, description="SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED")

    @field_validator("appointment_date")
    @classmethod
    def check_future_date(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v < date.today():
            raise ValueError(f"Appointment date cannot be in the past ({v} < {date.today()}).")
        return v

    @field_validator("appointment_time")
    @classmethod
    def check_time(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_time_format(v)
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"SCHEDULED", "COMPLETED", "CANCELLED", "RESCHEDULED"}
            v_upper = v.strip().upper()
            if v_upper not in allowed:
                raise ValueError(f"Invalid status '{v}'. Allowed values: {', '.join(sorted(allowed))}")
            return v_upper
        return v


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: date
    appointment_time: str
    status: str
    booking_reference: str
    created_at: datetime
    patient: Optional[PatientOut] = None
    doctor: Optional[DoctorOut] = None

    model_config = ConfigDict(from_attributes=True)
