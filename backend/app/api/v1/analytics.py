from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import AnalyticsOut

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("", response_model=AnalyticsOut)
async def get_analytics(
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Get aggregate operational analytics: appointment counts by status,
    patient counts, doctor workload breakdown, and call metrics.
    """
    return await service.get_analytics()

