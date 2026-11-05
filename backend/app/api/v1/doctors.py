from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.doctor_service import DoctorService
from app.schemas.doctor import DoctorOut
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/doctors", tags=["Doctors"])


def get_doctor_service(db: AsyncSession = Depends(get_db)) -> DoctorService:
    return DoctorService(db)


@router.get("", response_model=PaginatedResponse[DoctorOut])
async def list_doctors(
    specialization: Optional[str] = Query(None, description="Filter by doctor specialization (e.g. Cardiology)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    service: DoctorService = Depends(get_doctor_service),
):
    """
    List doctors with pagination and optional specialization/active filters.
    """
    return await service.list_doctors(
        specialization=specialization,
        is_active=is_active,
        page=page,
        size=size,
    )


@router.get("/{id}", response_model=DoctorOut)
async def get_doctor_by_id(
    id: int,
    service: DoctorService = Depends(get_doctor_service),
):
    """
    Get doctor details by ID.
    """
    return await service.get_doctor_by_id(id)
