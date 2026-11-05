from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.patient import Patient
from app.repositories.patient_repo import PatientRepository
from app.schemas.patient import PatientCreate, PatientOut


class PatientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.patient_repo = PatientRepository(db)

    async def create_patient(self, data: PatientCreate) -> PatientOut:
        # Check if already exists by phone
        existing = await self.patient_repo.get_by_phone(data.phone_number)
        if existing:
            # Update name if provided
            if data.name and existing.name != data.name:
                existing.name = data.name
            if data.email and not existing.email:
                existing.email = data.email
            await self.db.commit()
            await self.db.refresh(existing)
            return PatientOut.model_validate(existing)

        patient = Patient(
            name=data.name,
            phone_number=data.phone_number,
            email=data.email,
        )
        self.db.add(patient)
        await self.db.commit()
        await self.db.refresh(patient)
        return PatientOut.model_validate(patient)

    async def get_patient_by_id(self, patient_id: int) -> PatientOut:
        patient = await self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found."
            )
        return PatientOut.model_validate(patient)

