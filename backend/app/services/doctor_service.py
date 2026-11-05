import json
from datetime import date
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.repositories.doctor_repo import DoctorRepository
from app.repositories.appointment_repo import AppointmentRepository
from app.schemas.doctor import DoctorOut, DoctorAvailabilityOut, AvailabilitySlot
from app.schemas.pagination import PaginatedResponse


DEFAULT_SLOTS = [
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "14:00", "14:30",
    "15:00", "15:30", "16:00", "16:30"
]


class DoctorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doctor_repo = DoctorRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    async def list_doctors(
        self,
        specialization: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        size: int = 10,
    ) -> PaginatedResponse[DoctorOut]:
        offset = (page - 1) * size
        doctors, total = await self.doctor_repo.list_doctors(
            specialization=specialization,
            is_active=is_active,
            offset=offset,
            limit=size,
        )
        pages = (total + size - 1) // size if total > 0 else 0
        return PaginatedResponse(
            items=[DoctorOut.model_validate(d) for d in doctors],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_doctor_by_id(self, doctor_id: int) -> DoctorOut:
        doctor = await self.doctor_repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with ID {doctor_id} not found."
            )
        return DoctorOut.model_validate(doctor)

    async def get_availability(
        self,
        doctor_id: Optional[int] = None,
        target_date: Optional[date] = None,
    ) -> List[DoctorAvailabilityOut]:
        search_date = target_date or date.today()

        if doctor_id:
            doctor = await self.doctor_repo.get_by_id(doctor_id)
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Doctor with ID {doctor_id} not found."
                )
            doctors = [doctor]
        else:
            doctors = await self.doctor_repo.get_all_active()

        results: List[DoctorAvailabilityOut] = []

        for doc in doctors:
            # Parse availability from doctor profile
            configured_slots = DEFAULT_SLOTS
            try:
                avail_data = json.loads(doc.availability)
                if isinstance(avail_data, dict) and "slots" in avail_data:
                    configured_slots = avail_data["slots"]
                elif isinstance(avail_data, list):
                    configured_slots = avail_data
            except Exception:
                pass

            # Fetch already booked times on this date for this doctor
            booked_times = set(await self.appointment_repo.get_doctor_booked_times(doc.id, search_date))

            slots = [
                AvailabilitySlot(
                    time=t,
                    is_available=(t not in booked_times)
                )
                for t in configured_slots
            ]

            results.append(
                DoctorAvailabilityOut(
                    doctor_id=doc.id,
                    doctor_name=doc.name,
                    specialization=doc.specialization,
                    date=search_date,
                    slots=slots,
                )
            )

        return results

