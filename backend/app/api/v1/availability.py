from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.doctor_service import DoctorService
from app.schemas.doctor import DoctorAvailabilityOut

router = APIRouter(prefix="/availability", tags=["Availability"])


def get_doctor_service(db: AsyncSession = Depends(get_db)) -> DoctorService:
    return DoctorService(db)


@router.get("", response_model=List[DoctorAvailabilityOut])
async def get_doctor_availability(
    doctor_id: Optional[int] = Query(None, description="Doctor ID (optional)"),
    date: Optional[date] = Query(None, description="Target appointment date (YYYY-MM-DD, defaults to today)"),
    service: DoctorService = Depends(get_doctor_service),
):
    """
    Check doctor appointment slot availability for a given date.
    Returns slots with is_available=True or False.
    """
    return await service.get_availability(doctor_id=doctor_id, target_date=date)

