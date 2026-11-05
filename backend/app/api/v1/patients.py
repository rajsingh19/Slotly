from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.patient_service import PatientService
from app.schemas.patient import PatientCreate, PatientOut

router = APIRouter(prefix="/patients", tags=["Patients"])


def get_patient_service(db: AsyncSession = Depends(get_db)) -> PatientService:
    return PatientService(db)


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    service: PatientService = Depends(get_patient_service),
):
    """
    Register a patient with phone number and optional email.
    Validates phone number format (10-15 digits).
    """
    return await service.create_patient(payload)


@router.get("/{id}", response_model=PatientOut)
async def get_patient_by_id(
    id: int,
    service: PatientService = Depends(get_patient_service),
):
    """
    Retrieve patient details by ID.
    """
    return await service.get_patient_by_id(id)
