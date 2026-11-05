from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class CallLog(Base, TimestampMixin):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    caller_phone = Column(String(30), nullable=True, index=True)
    caller_name = Column(String(100), nullable=True)
    status = Column(String(20), default="COMPLETED")  # ACTIVE, COMPLETED, DROPPED, TRANSFERRED
    intent = Column(String(50), nullable=True)        # BOOKING, RESCHEDULE, CANCEL, INQUIRY, EMERGENCY
    duration_seconds = Column(Integer, default=0)
    summary = Column(Text, nullable=True)

    transcripts = relationship("CallTranscript", back_populates="call_log", cascade="all, delete-orphan")


class CallTranscript(Base, TimestampMixin):
    __tablename__ = "call_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_log_id = Column(Integer, ForeignKey("call_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker = Column(String(20), nullable=False)  # "user" or "assistant"
    message = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    call_log = relationship("CallLog", back_populates="transcripts")
