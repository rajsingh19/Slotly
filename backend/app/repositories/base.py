from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: Type[ModelT], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: int) -> Optional[ModelT]:
        stmt = select(self.model).where(self.model.id == id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def list_all(self, offset: int = 0, limit: int = 10) -> List[ModelT]:
        stmt = select(self.model).offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def count_all(self) -> int:
        stmt = select(func.count(self.model.id))
        res = await self.db.execute(stmt)
        return res.scalar() or 0

    async def create(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.db.delete(entity)
        await self.db.flush()

