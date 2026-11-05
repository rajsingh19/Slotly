from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings
from app.schemas.health import HealthCheck

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheck)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    System and database health check endpoint.
    """
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    overall_status = "ok" if db_status == "healthy" else "degraded"

    return HealthCheck(
        status=overall_status,
        database=db_status,
        version=settings.VERSION,
        timestamp=datetime.utcnow()
    )
