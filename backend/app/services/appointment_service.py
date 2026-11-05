from datetime import date
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.appointment import Appointment, generate_booking_reference
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.doctor_repo import DoctorRepository
from app.repositories.patient_repo import PatientRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut
from app.schemas.pagination import PaginatedResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
        self.doctor_repo = DoctorRepository(db)
        self.patient_repo = PatientRepository(db)

    async def create_appointment(self, data: AppointmentCreate) -> AppointmentOut:
        # 1. Validate appointment date
        if data.appointment_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Appointment date cannot be in the past ({data.appointment_date})."
            )

        # 2. Validate Doctor exists and is active
        doctor = await self.doctor_repo.get_by_id(data.doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor #{data.doctor_id} not found."
            )
        if not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor #{doctor.name} is currently not accepting appointments."
            )

        # 3. Resolve or create Patient
        if data.patient_id:
            patient = await self.patient_repo.get_by_id(data.patient_id)
            if not patient:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Patient #{data.patient_id} not found."
                )
        else:
            # Create or fetch by phone
            patient = await self.patient_repo.get_or_create_patient(
                name=data.patient_name or "Guest Patient",
                phone_number=data.patient_phone or "+15550000000",
                email=data.patient_email,
            )

        # 4. Check for double booking (Doctor cannot have another active appointment at same date/time)
        conflict_doc = await self.appointment_repo.check_doctor_double_booking(
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            appointment_time=data.appointment_time,
        )
        if conflict_doc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Double booking prevented: {doctor.name} is already booked on {data.appointment_date} at {data.appointment_time}."
            )

        # 5. Check for duplicate appointment (Patient cannot have overlapping appointment at same date/time)
        conflict_patient = await self.appointment_repo.check_patient_duplicate_booking(
            patient_id=patient.id,
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            appointment_time=data.appointment_time,
        )
        if conflict_patient:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate appointment: Patient {patient.name} already has an active appointment on {data.appointment_date} at {data.appointment_time} (Ref: {conflict_patient.booking_reference})."
            )

        # 6. Database Transaction: insert appointment atomically
        try:
            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=data.appointment_date,
                appointment_time=data.appointment_time,
                status="SCHEDULED",
                booking_reference=generate_booking_reference(),
            )
            self.db.add(appointment)
            await self.db.commit()
            await self.db.refresh(appointment)
        except IntegrityError as ie:
            await self.db.rollback()
            logger.warning(f"Concurrency conflict during appointment booking: {ie}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This doctor slot has already been booked by another request. Please choose a different time slot."
            )
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to book appointment: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to book appointment due to database error."
            )

        # Reload with relations
        reloaded = await self.appointment_repo.get_by_id_with_relations(appointment.id)
        logger.info(
            f"Appointment created: {reloaded.booking_reference} for {reloaded.patient.name} with {reloaded.doctor.name} on {reloaded.appointment_date} at {reloaded.appointment_time}"
        )
        return AppointmentOut.model_validate(reloaded)

    async def list_appointments(
        self,
        doctor_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        appointment_date: Optional[date] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        size: int = 10,
    ) -> PaginatedResponse[AppointmentOut]:
        offset = (page - 1) * size
        appointments, total = await self.appointment_repo.list_appointments(
            doctor_id=doctor_id,
            patient_id=patient_id,
            appointment_date=appointment_date,
            status=status_filter,
            offset=offset,
            limit=size,
        )
        pages = (total + size - 1) // size if total > 0 else 0
        return PaginatedResponse(
            items=[AppointmentOut.model_validate(a) for a in appointments],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_appointment_by_id(self, appointment_id: int) -> AppointmentOut:
        appointment = await self.appointment_repo.get_by_id_with_relations(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment #{appointment_id} not found."
            )
        return AppointmentOut.model_validate(appointment)

    async def update_appointment(
        self,
        appointment_id: int,
        data: AppointmentUpdate
    ) -> AppointmentOut:
        appointment = await self.appointment_repo.get_by_id_with_relations(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment #{appointment_id} not found."
            )

        if appointment.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify a cancelled appointment. Please book a new appointment."
            )

        new_date = data.appointment_date or appointment.appointment_date
        new_time = data.appointment_time or appointment.appointment_time

        # If date or time changed, check double booking
        if data.appointment_date or data.appointment_time:
            if new_date < date.today():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot reschedule to a past date ({new_date})."
                )

            conflict_doc = await self.appointment_repo.check_doctor_double_booking(
                doctor_id=appointment.doctor_id,
                appointment_date=new_date,
                appointment_time=new_time,
                exclude_id=appointment.id,
            )
            if conflict_doc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot reschedule: Doctor is already booked on {new_date} at {new_time}."
                )

            appointment.appointment_date = new_date
            appointment.appointment_time = new_time
            appointment.status = "RESCHEDULED"

        if data.status:
            appointment.status = data.status

        try:
            await self.db.commit()
            await self.db.refresh(appointment)
        except IntegrityError as ie:
            await self.db.rollback()
            logger.warning(f"Concurrency conflict during appointment update: {ie}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This doctor slot has already been booked by another request. Please choose a different time slot."
            )
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update appointment: {str(e)}"
            )

        reloaded = await self.appointment_repo.get_by_id_with_relations(appointment.id)
        return AppointmentOut.model_validate(reloaded)

    async def delete_appointment(self, appointment_id: int) -> dict:
        appointment = await self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment #{appointment_id} not found."
            )

        # Soft cancel to free slot and retain history
        appointment.status = "CANCELLED"
        await self.db.commit()

        logger.info(f"Appointment #{appointment_id} ({appointment.booking_reference}) marked as CANCELLED.")
        return {
            "success": True,
            "message": f"Appointment #{appointment_id} ({appointment.booking_reference}) has been successfully cancelled."
        }

    async def get_by_reference(self, reference: str) -> Optional[AppointmentOut]:
        apt = await self.appointment_repo.get_by_reference(reference.strip().upper())
        if not apt:
            return None
        return AppointmentOut.model_validate(apt)

    async def find_appointment_by_ref_or_phone(self, identifier: str) -> Optional[Appointment]:
        cleaned = identifier.strip()
        if cleaned.upper().startswith("APT-"):
            return await self.appointment_repo.get_by_reference(cleaned.upper())
        # Try as phone number or numeric ID
        if cleaned.isdigit():
            apt = await self.appointment_repo.get_by_id_with_relations(int(cleaned))
            if apt:
                return apt
        return await self.appointment_repo.get_latest_active_by_patient_phone(cleaned)

