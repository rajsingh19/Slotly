from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    caller_number = Column(String(30), nullable=False, index=True)
    call_direction = Column(String(20), default="INBOUND", nullable=False)  # INBOUND, OUTBOUND
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0, nullable=False)
    transcript = Column(Text, nullable=True)
    status = Column(String(30), default="COMPLETED", nullable=False, index=True)  # ACTIVE, COMPLETED, FAILED, DROPPED
    estimated_cost = Column(Float, default=0.0, nullable=False)

    events = relationship("CallEvent", back_populates="call_session", cascade="all, delete-orphan")


class CallEvent(Base):
    __tablename__ = "call_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # SPEECH_RECOGNIZED, TOOL_CALLED, APPOINTMENT_BOOKED, etc.
    event_data = Column(Text, nullable=True)  # JSON or text payload
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    call_session = relationship("CallSession", back_populates="events")
