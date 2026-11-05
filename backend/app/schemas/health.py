from datetime import datetime
from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: str = "ok"
    database: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime

