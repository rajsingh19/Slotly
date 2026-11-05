from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.models.call_session import CallSession, CallEvent
from app.repositories.base import BaseRepository


class CallSessionRepository(BaseRepository[CallSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(CallSession, db)

    async def list_calls(
        self,
        caller_number: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[CallSession], int]:
        filters = []
        if caller_number:
            filters.append(CallSession.caller_number.ilike(f"%{caller_number.strip()}%"))
        if status:
            filters.append(CallSession.status == status.strip().upper())

        # Count
        count_stmt = select(func.count(CallSession.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Query
        query_stmt = select(CallSession).options(selectinload(CallSession.events))
        if filters:
            query_stmt = query_stmt.where(and_(*filters))
        query_stmt = query_stmt.order_by(CallSession.started_at.desc()).offset(offset).limit(limit)

        res = await self.db.execute(query_stmt)
        items = list(res.scalars().all())

        return items, total

    async def add_event(
        self,
        call_session_id: int,
        event_type: str,
        event_data: Optional[str] = None
    ) -> CallEvent:
        event = CallEvent(
            call_session_id=call_session_id,
            event_type=event_type,
            event_data=event_data,
        )
        self.db.add(event)
        await self.db.flush()
        return event
