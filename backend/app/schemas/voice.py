from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field


class VoiceSessionStart(BaseModel):
    caller_phone: Optional[str] = None
    caller_name: Optional[str] = None
    source: Literal["browser", "plivo", "simulator"] = "browser"


class VoiceFrame(BaseModel):
    """
    Standard voice frame model representing Pipecat/WebSocket audio & control packets.
    """
    type: Literal["audio", "text", "control", "status", "action", "error"]
    data: Optional[str] = None           # Base64 audio chunk or text content
    sample_rate: int = 16000
    format: str = "wav"                  # "wav", "pcm", "mp3"
    role: Optional[Literal["user", "assistant", "system"]] = None
    action_type: Optional[str] = None    # e.g., "BOOKING_CONFIRMED", "DOCTOR_FOUND", "CALL_ENDED"
    action_payload: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None
    is_final: bool = False


class DialogueTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
