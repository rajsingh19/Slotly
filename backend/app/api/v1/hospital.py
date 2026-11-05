from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.hospital_repo import HospitalRepository
from app.schemas.hospital import HospitalOut

router = APIRouter(prefix="/hospital", tags=["Hospital"])


@router.get("", response_model=HospitalOut)
async def get_hospital_info(
    db: AsyncSession = Depends(get_db)
):
    """
    Get primary hospital organization details (id, name, address, contact_number).
    """
    repo = HospitalRepository(db)
    hospital = await repo.get_primary_hospital()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital information not found."
        )
    return HospitalOut.model_validate(hospital)
