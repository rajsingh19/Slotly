from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.repositories.base import BaseRepository


ACTIVE_STATUSES = ["SCHEDULED", "RESCHEDULED"]


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self, db: AsyncSession):
        super().__init__(Appointment, db)

    async def get_by_id_with_relations(self, id: int) -> Optional[Appointment]:
        stmt = select(Appointment).where(Appointment.id == id).options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor)
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def get_by_reference(self, reference: str) -> Optional[Appointment]:
        stmt = select(Appointment).where(Appointment.booking_reference == reference).options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor)
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def check_doctor_double_booking(
        self,
        doctor_id: int,
        appointment_date: date,
        appointment_time: str,
        exclude_id: Optional[int] = None,
    ) -> Optional[Appointment]:
        """
        Check if the doctor is already booked at this date and time for an active appointment.
        """
        filters = [
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.appointment_time == appointment_time,
            Appointment.status.in_(ACTIVE_STATUSES),
        ]
        if exclude_id is not None:
            filters.append(Appointment.id != exclude_id)

        stmt = select(Appointment).where(and_(*filters))
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def check_patient_duplicate_booking(
        self,
        patient_id: int,
        doctor_id: int,
        appointment_date: date,
        appointment_time: str,
        exclude_id: Optional[int] = None,
    ) -> Optional[Appointment]:
        """
        Check if the patient already has an active appointment at the exact same date and time.
        """
        filters = [
            Appointment.patient_id == patient_id,
            Appointment.appointment_date == appointment_date,
            Appointment.appointment_time == appointment_time,
            Appointment.status.in_(ACTIVE_STATUSES),
        ]
        if exclude_id is not None:
            filters.append(Appointment.id != exclude_id)

        stmt = select(Appointment).where(and_(*filters))
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def list_appointments(
        self,
        doctor_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        appointment_date: Optional[date] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Appointment], int]:
        filters = []
        if doctor_id is not None:
            filters.append(Appointment.doctor_id == doctor_id)
        if patient_id is not None:
            filters.append(Appointment.patient_id == patient_id)
        if appointment_date is not None:
            filters.append(Appointment.appointment_date == appointment_date)
        if status is not None:
            filters.append(Appointment.status == status.strip().upper())

        # Count
        count_stmt = select(func.count(Appointment.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Query
        query_stmt = select(Appointment).options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor)
        )
        if filters:
            query_stmt = query_stmt.where(and_(*filters))
        query_stmt = query_stmt.order_by(
            Appointment.appointment_date.desc(),
            Appointment.appointment_time.asc()
        ).offset(offset).limit(limit)

        res = await self.db.execute(query_stmt)
        items = list(res.scalars().all())

        return items, total

    async def get_doctor_booked_times(
        self,
        doctor_id: int,
        appointment_date: date,
    ) -> List[str]:
        """
        Return list of already booked times for a doctor on a given date.
        """
        stmt = select(Appointment.appointment_time).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == appointment_date,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
