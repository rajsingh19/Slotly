from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor, TimeSlot
from app.models.appointment import Appointment, generate_appointment_number
from app.models.hospital import Department, HospitalFAQ, EmergencyProtocol
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule, AppointmentCancel
from app.core.logging import get_logger

logger = get_logger(__name__)


class HospitalService:
    """
    Hospital domain business service handling doctors, availability,
    appointment booking, rescheduling, cancellations, and hospital knowledge retrieval.
    """

    async def list_departments(self, db: AsyncSession) -> List[Department]:
        result = await db.execute(select(Department).where(Department.is_active == True))
        return list(result.scalars().all())

    async def list_faqs(self, db: AsyncSession, query: Optional[str] = None) -> List[HospitalFAQ]:
        stmt = select(HospitalFAQ).where(HospitalFAQ.is_active == True)
        if query:
            q_lower = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    HospitalFAQ.question.ilike(q_lower),
                    HospitalFAQ.answer.ilike(q_lower),
                    HospitalFAQ.keywords.ilike(q_lower),
                    HospitalFAQ.category.ilike(q_lower),
                )
            )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_doctors(
        self,
        db: AsyncSession,
        specialty: Optional[str] = None,
        department: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Doctor]:
        stmt = select(Doctor).where(Doctor.is_active == True).options(selectinload(Doctor.slots))
        if specialty:
            stmt = stmt.where(Doctor.specialty.ilike(f"%{specialty}%"))
        if department:
            stmt = stmt.where(Doctor.department.ilike(f"%{department}%"))
        if query:
            q_lower = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    Doctor.name.ilike(q_lower),
                    Doctor.specialty.ilike(q_lower),
                    Doctor.department.ilike(q_lower),
                )
            )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_doctor_by_id(self, db: AsyncSession, doctor_id: int) -> Optional[Doctor]:
        stmt = select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.slots))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_available_slots(
        self,
        db: AsyncSession,
        doctor_id: Optional[int] = None,
        specialty: Optional[str] = None,
        target_date: Optional[date] = None,
    ) -> List[TimeSlot]:
        stmt = select(TimeSlot).join(Doctor).where(
            and_(
                TimeSlot.is_booked == False,
                Doctor.is_active == True
            )
        ).options(selectinload(TimeSlot.doctor))

        if doctor_id:
            stmt = stmt.where(TimeSlot.doctor_id == doctor_id)
        if specialty:
            stmt = stmt.where(Doctor.specialty.ilike(f"%{specialty}%"))
        if target_date:
            stmt = stmt.where(TimeSlot.slot_date == target_date)
        else:
            # Default to today or future
            stmt = stmt.where(TimeSlot.slot_date >= date.today())

        stmt = stmt.order_by(TimeSlot.slot_date.asc(), TimeSlot.start_time.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def book_appointment(
        self,
        db: AsyncSession,
        data: AppointmentCreate
    ) -> Appointment:
        # Check slot availability
        slot_stmt = select(TimeSlot).where(
            and_(
                TimeSlot.id == data.slot_id,
                TimeSlot.doctor_id == data.doctor_id
            )
        )
        if db.bind and db.bind.dialect.name != "sqlite":
            slot_stmt = slot_stmt.with_for_update()
        result = await db.execute(slot_stmt)
        slot = result.scalars().first()

        if not slot:
            raise ValueError(f"Time slot #{data.slot_id} not found for doctor #{data.doctor_id}.")
        if slot.is_booked:
            raise ValueError(f"Time slot #{data.slot_id} on {slot.slot_date} at {slot.start_time} is already booked.")

        # Mark slot as booked
        slot.is_booked = True

        # Create appointment record
        appointment = Appointment(
            appointment_number=generate_appointment_number(),
            patient_name=data.patient_name,
            patient_phone=data.patient_phone,
            patient_email=data.patient_email,
            patient_age=data.patient_age,
            patient_gender=data.patient_gender,
            doctor_id=data.doctor_id,
            slot_id=slot.id,
            appointment_date=slot.slot_date,
            appointment_time=f"{slot.start_time} - {slot.end_time}",
            status="CONFIRMED",
            reason_for_visit=data.reason_for_visit,
            notes=data.notes,
        )

        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)

        # Load doctor relationship
        doc_stmt = select(Appointment).where(Appointment.id == appointment.id).options(selectinload(Appointment.doctor))
        res = await db.execute(doc_stmt)
        refreshed = res.scalars().first()

        logger.info(
            f"Appointment booked: {refreshed.appointment_number} for {refreshed.patient_name} on {refreshed.appointment_date} at {refreshed.appointment_time}",
            extra={"action": "BOOKING_CONFIRMED", "patient_phone": refreshed.patient_phone}
        )
        return refreshed

    async def reschedule_appointment(
        self,
        db: AsyncSession,
        appointment_identifier: str,  # either appointment_number or id as str
        new_slot_id: int,
        reason: Optional[str] = None
    ) -> Appointment:
        # Find appointment by ID or appointment_number
        stmt = select(Appointment).where(
            or_(
                Appointment.appointment_number == appointment_identifier,
                Appointment.id == (int(appointment_identifier) if appointment_identifier.isdigit() else -1)
            )
        ).options(selectinload(Appointment.doctor))
        result = await db.execute(stmt)
        appointment = result.scalars().first()

        if not appointment:
            raise ValueError(f"Appointment '{appointment_identifier}' not found.")

        if appointment.status == "CANCELLED":
            raise ValueError("Cannot reschedule a cancelled appointment. Please book a new appointment.")

        # Find new slot
        new_slot_stmt = select(TimeSlot).where(TimeSlot.id == new_slot_id)
        if db.bind and db.bind.dialect.name != "sqlite":
            new_slot_stmt = new_slot_stmt.with_for_update()
        new_slot_res = await db.execute(new_slot_stmt)
        new_slot = new_slot_res.scalars().first()

        if not new_slot:
            raise ValueError(f"Target slot #{new_slot_id} not found.")
        if new_slot.is_booked:
            raise ValueError(f"Target slot #{new_slot_id} on {new_slot.slot_date} at {new_slot.start_time} is already booked.")

        # Free old slot if attached
        if appointment.slot_id:
            old_slot_stmt = select(TimeSlot).where(TimeSlot.id == appointment.slot_id)
            old_slot_res = await db.execute(old_slot_stmt)
            old_slot = old_slot_res.scalars().first()
            if old_slot:
                old_slot.is_booked = False

        # Book new slot
        new_slot.is_booked = True

        # Update appointment
        appointment.slot_id = new_slot.id
        appointment.doctor_id = new_slot.doctor_id
        appointment.appointment_date = new_slot.slot_date
        appointment.appointment_time = f"{new_slot.start_time} - {new_slot.end_time}"
        appointment.status = "RESCHEDULED"
        if reason:
            appointment.notes = f"{appointment.notes or ''} [Rescheduled: {reason}]".strip()

        await db.commit()
        await db.refresh(appointment)

        # Reload with doctor
        doc_stmt = select(Appointment).where(Appointment.id == appointment.id).options(selectinload(Appointment.doctor))
        res = await db.execute(doc_stmt)
        refreshed = res.scalars().first()

        logger.info(
            f"Appointment rescheduled: {refreshed.appointment_number} new date: {refreshed.appointment_date} at {refreshed.appointment_time}",
            extra={"action": "APPOINTMENT_RESCHEDULED", "patient_phone": refreshed.patient_phone}
        )
        return refreshed

    async def cancel_appointment(
        self,
        db: AsyncSession,
        appointment_identifier: str,
        reason: Optional[str] = None
    ) -> Appointment:
        stmt = select(Appointment).where(
            or_(
                Appointment.appointment_number == appointment_identifier,
                Appointment.id == (int(appointment_identifier) if appointment_identifier.isdigit() else -1)
            )
        ).options(selectinload(Appointment.doctor))
        result = await db.execute(stmt)
        appointment = result.scalars().first()

        if not appointment:
            raise ValueError(f"Appointment '{appointment_identifier}' not found.")

        if appointment.status == "CANCELLED":
            return appointment

        # Free up slot
        if appointment.slot_id:
            slot_stmt = select(TimeSlot).where(TimeSlot.id == appointment.slot_id)
            slot_res = await db.execute(slot_stmt)
            slot = slot_res.scalars().first()
            if slot:
                slot.is_booked = False

        appointment.status = "CANCELLED"
        if reason:
            appointment.notes = f"{appointment.notes or ''} [Cancelled: {reason}]".strip()

        await db.commit()
        await db.refresh(appointment)

        logger.info(
            f"Appointment cancelled: {appointment.appointment_number}",
            extra={"action": "APPOINTMENT_CANCELLED", "patient_phone": appointment.patient_phone}
        )
        return appointment

    async def find_appointments_by_phone(
        self,
        db: AsyncSession,
        phone: str
    ) -> List[Appointment]:
        raw_phone = phone.strip()
        clean_digits = "".join(filter(str.isdigit, phone))
        stmt = select(Appointment).where(
            or_(
                Appointment.patient_phone.ilike(f"%{raw_phone}%"),
                Appointment.patient_phone.ilike(f"%{clean_digits}%"),
            )
        ).options(selectinload(Appointment.doctor)).order_by(Appointment.appointment_date.desc())
        result = await db.execute(stmt)
        records = list(result.scalars().all())
        if not records and clean_digits:
            all_stmt = select(Appointment).options(selectinload(Appointment.doctor))
            all_res = await db.execute(all_stmt)
            for a in all_res.scalars().all():
                a_digits = "".join(filter(str.isdigit, a.patient_phone or ""))
                if clean_digits in a_digits or a_digits in clean_digits:
                    records.append(a)
        return records

    async def list_recent_appointments(
        self,
        db: AsyncSession,
        limit: int = 50
    ) -> List[Appointment]:
        stmt = select(Appointment).options(selectinload(Appointment.doctor)).order_by(Appointment.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


hospital_service = HospitalService()
