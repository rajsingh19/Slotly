from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.call_service import CallService
from app.schemas.call_session import CallSessionCreate, CallSessionOut, CallEventOut
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/calls", tags=["Calls"])


def get_call_service(db: AsyncSession = Depends(get_db)) -> CallService:
    return CallService(db)


@router.get("", response_model=PaginatedResponse[CallSessionOut])
async def list_calls(
    caller_number: Optional[str] = Query(None, description="Filter by caller phone number"),
    status: Optional[str] = Query(None, description="Filter by call status (ACTIVE, COMPLETED, FAILED)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    service: CallService = Depends(get_call_service),
):
    """
    List call sessions with pagination and filters.
    """
    return await service.list_calls(
        caller_number=caller_number,
        status_filter=status,
        page=page,
        size=size,
    )


@router.post("", response_model=CallSessionOut, status_code=status.HTTP_201_CREATED)
async def create_call(
    payload: CallSessionCreate,
    service: CallService = Depends(get_call_service),
):
    """
    Record a new call session.
    """
    return await service.create_call_session(payload)


@router.post("/{id}/events", response_model=CallEventOut, status_code=status.HTTP_201_CREATED)
async def add_call_event(
    id: int,
    event_type: str = Query(..., description="Event type, e.g. SPEECH_RECOGNIZED, TOOL_CALLED"),
    event_data: Optional[str] = Query(None, description="Event data JSON or text"),
    service: CallService = Depends(get_call_service),
):
    """
    Record an event in the call session trajectory.
    """
    return await service.add_call_event(id, event_type, event_data)
