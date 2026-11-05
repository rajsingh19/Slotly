from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.patient import Patient
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    def __init__(self, db: AsyncSession):
        super().__init__(Patient, db)

    async def get_by_phone(self, phone_number: str) -> Optional[Patient]:
        stmt = select(Patient).where(Patient.phone_number == phone_number)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def get_or_create_patient(
        self,
        name: str,
        phone_number: str,
        email: Optional[str] = None
    ) -> Patient:
        patient = await self.get_by_phone(phone_number)
        if patient:
            # Update name / email if provided
            if name and patient.name != name:
                patient.name = name
            if email and not patient.email:
                patient.email = email
            await self.db.flush()
            return patient

        new_patient = Patient(
            name=name,
            phone_number=phone_number,
            email=email,
        )
        self.db.add(new_patient)
        await self.db.flush()
        return new_patient
