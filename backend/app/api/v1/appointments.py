from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def get_appointment_service(db: AsyncSession = Depends(get_db)) -> AppointmentService:
    return AppointmentService(db)


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    service: AppointmentService = Depends(get_appointment_service),
):
    """
    Book an appointment.
    Prevents duplicate appointments and double booking for the same doctor and time slot.
    Uses database transactions and validates dates and phone numbers.
    """
    return await service.create_appointment(payload)


@router.get("", response_model=PaginatedResponse[AppointmentOut])
async def list_appointments(
    doctor_id: Optional[int] = Query(None, description="Filter by Doctor ID"),
    patient_id: Optional[int] = Query(None, description="Filter by Patient ID"),
    appointment_date: Optional[date] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    service: AppointmentService = Depends(get_appointment_service),
):
    """
    List appointments with pagination and filters.
    """
    return await service.list_appointments(
        doctor_id=doctor_id,
        patient_id=patient_id,
        appointment_date=appointment_date,
        status_filter=status,
        page=page,
        size=size,
    )


@router.get("/{id}", response_model=AppointmentOut)
async def get_appointment_by_id(
    id: int,
    service: AppointmentService = Depends(get_appointment_service),
):
    """
    Get appointment details by ID.
    """
    return await service.get_appointment_by_id(id)


@router.patch("/{id}", response_model=AppointmentOut)
async def update_appointment(
    id: int,
    payload: AppointmentUpdate,
    service: AppointmentService = Depends(get_appointment_service),
):
    """
    Reschedule or update appointment status.
    Validates new date/time and prevents double booking.
    """
    return await service.update_appointment(id, payload)


@router.delete("/{id}")
async def cancel_appointment(
    id: int,
    service: AppointmentService = Depends(get_appointment_service),
):
    """
    Cancel an appointment and free up the doctor's time slot.
    """
    return await service.delete_appointment(id)
