import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_phone_format(v: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)\.]", "", v)
    # Check if begins with optional + and has between 10 and 15 digits
    match = re.match(r"^\+?[0-9]{10,15}$", cleaned)
    if not match:
        raise ValueError("Invalid phone number format. Must contain 10-15 digits (e.g. +15551234567 or 5551234567)")
    return cleaned


class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., description="Patient contact phone number (10-15 digits)")
    email: Optional[str] = Field(None, max_length=100)

    @field_validator("phone_number")
    @classmethod
    def check_phone_number(cls, v: str) -> str:
        return validate_phone_format(v)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = v.strip().lower()
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", v):
                raise ValueError("Invalid email address format.")
        return v


class PatientCreate(PatientBase):
    pass


class PatientOut(PatientBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

