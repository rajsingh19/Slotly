import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def generate_booking_reference() -> str:
    today_str = datetime.utcnow().strftime("%Y%m%d")
    short_code = uuid.uuid4().hex[:6].upper()
    return f"APT-{today_str}-{short_code}"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_date = Column(Date, nullable=False, index=True)
    appointment_time = Column(String(20), nullable=False, index=True)  # e.g., "09:00", "09:30"
    status = Column(String(20), default="SCHEDULED", nullable=False, index=True)  # SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED
    booking_reference = Column(String(32), unique=True, index=True, nullable=False, default=generate_booking_reference)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")

    __table_args__ = (
        Index("ix_appointments_doctor_date_time", "doctor_id", "appointment_date", "appointment_time"),
        Index("ix_appointments_patient_date", "patient_id", "appointment_date"),
    )
