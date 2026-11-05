from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.doctor import Doctor
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):
    def __init__(self, db: AsyncSession):
        super().__init__(Doctor, db)

    async def list_doctors(
        self,
        specialization: Optional[str] = None,
        is_active: Optional[bool] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Doctor], int]:
        filters = []
        if specialization:
            filters.append(Doctor.specialization.ilike(f"%{specialization.strip()}%"))
        if is_active is not None:
            filters.append(Doctor.is_active == is_active)

        # Count total
        count_stmt = select(func.count(Doctor.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Query items
        query_stmt = select(Doctor)
        if filters:
            query_stmt = query_stmt.where(and_(*filters))
        query_stmt = query_stmt.order_by(Doctor.name.asc()).offset(offset).limit(limit)

        result = await self.db.execute(query_stmt)
        doctors = list(result.scalars().all())

        return doctors, total

    async def get_all_active(self) -> List[Doctor]:
        stmt = select(Doctor).where(Doctor.is_active == True).order_by(Doctor.name.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
