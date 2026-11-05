from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False, index=True)
    availability = Column(Text, nullable=False)  # JSON-encoded days and slots
    consultation_fee = Column(Float, default=50.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
