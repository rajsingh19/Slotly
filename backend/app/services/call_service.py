from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.call_session import CallSession, CallEvent
from app.repositories.call_session_repo import CallSessionRepository
from app.schemas.call_session import CallSessionCreate, CallSessionOut, CallEventOut
from app.schemas.pagination import PaginatedResponse


class CallService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.call_repo = CallSessionRepository(db)

    async def list_calls(
        self,
        caller_number: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        size: int = 10,
    ) -> PaginatedResponse[CallSessionOut]:
        offset = (page - 1) * size
        calls, total = await self.call_repo.list_calls(
            caller_number=caller_number,
            status=status_filter,
            offset=offset,
            limit=size,
        )
        pages = (total + size - 1) // size if total > 0 else 0
        return PaginatedResponse(
            items=[CallSessionOut.model_validate(c) for c in calls],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def create_call_session(self, data: CallSessionCreate) -> CallSessionOut:
        session = CallSession(
            caller_number=data.caller_number,
            call_direction=data.call_direction,
            transcript=data.transcript,
            status=data.status,
            estimated_cost=data.estimated_cost,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return CallSessionOut.model_validate(session)

    async def add_call_event(
        self,
        call_session_id: int,
        event_type: str,
        event_data: Optional[str] = None
    ) -> CallEventOut:
        event = await self.call_repo.add_event(call_session_id, event_type, event_data)
        await self.db.commit()
        await self.db.refresh(event)
        return CallEventOut.model_validate(event)
