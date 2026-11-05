from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.hospital import Hospital
from app.repositories.base import BaseRepository


class HospitalRepository(BaseRepository[Hospital]):
    def __init__(self, db: AsyncSession):
        super().__init__(Hospital, db)

    async def get_primary_hospital(self) -> Optional[Hospital]:
        stmt = select(Hospital).order_by(Hospital.id.asc()).limit(1)
        res = await self.db.execute(stmt)
        return res.scalars().first()

