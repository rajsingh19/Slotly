from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: str = "Operation successful"
    data: Optional[DataT] = None
    meta: Optional[dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    environment: str = "development"
    database: str = "healthy"
    cache: str = "healthy"
    voice_stt: str = "ready"
    voice_tts: str = "ready"
    llm_provider: str = "ready"
    uptime_seconds: float = 0.0
