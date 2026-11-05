import base64
import time
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from app.api.deps import get_database_session, get_voice_pipeline
from app.services.voice.pipeline import VoicePipelineOrchestrator, VoiceSessionState
from app.schemas.common import APIResponse
from app.schemas.voice import VoiceFrame, VoiceSessionStart
from app.models.call_log import CallLog

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Agent"])

# In-memory registry of active live sessions
active_sessions: dict[str, VoiceSessionState] = {}


@router.post("/session", response_model=APIResponse[dict])
async def create_voice_session(
    payload: VoiceSessionStart = VoiceSessionStart(),
    db: AsyncSession = Depends(get_database_session),
    pipeline: VoicePipelineOrchestrator = Depends(get_voice_pipeline)
):
    session_id = f"call-{uuid.uuid4().hex[:10]}"
    state = VoiceSessionState(session_id=session_id, caller_phone=payload.caller_phone)
    active_sessions[session_id] = state

    await pipeline.initialize_call(db, session_id, payload.caller_phone)

    welcome_text = f"Hello! Thank you for calling {settings.HOSPITAL_NAME}. I am Maya, your AI voice assistant. How may I help you today?"

    return APIResponse(
        success=True,
        message="Voice session established",
        data={
            "session_id": session_id,
            "welcome_message": welcome_text,
            "ws_url": f"/api/v1/voice/ws/{session_id}"
        }
    )


@router.post("/simulate-turn", response_model=APIResponse[dict])
async def simulate_turn(
    session_id: str,
    message: str,
    db: AsyncSession = Depends(get_database_session),
    pipeline: VoicePipelineOrchestrator = Depends(get_voice_pipeline)
):
    """
    REST endpoint to simulate or process a voice dialogue turn.
    Useful for testing, automated tests, or text-based fallback chat.
    """
    if session_id not in active_sessions:
        active_sessions[session_id] = VoiceSessionState(session_id=session_id)

    state = active_sessions[session_id]
    reply = await pipeline.process_user_turn(db, state, websocket=None, user_text=message)

    return APIResponse(
        success=True,
        message="Turn processed",
        data={
            "session_id": session_id,
            "user_message": message,
            "assistant_reply": reply
        }
    )


@router.get("/calls", response_model=APIResponse[List[dict]])
async def list_recent_calls(
    limit: int = 20,
    db: AsyncSession = Depends(get_database_session)
):
    stmt = select(CallLog).options(selectinload(CallLog.transcripts)).order_by(CallLog.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    calls = res.scalars().all()

    formatted = []
    for c in calls:
        formatted.append({
            "id": c.id,
            "session_id": c.session_id,
            "caller_phone": c.caller_phone,
            "status": c.status,
            "duration_seconds": c.duration_seconds,
            "turn_count": len(c.transcripts),
            "created_at": c.created_at.isoformat(),
            "transcripts": [
                {"speaker": t.speaker, "message": t.message, "latency_ms": t.latency_ms}
                for t in c.transcripts
            ]
        })

    return APIResponse(
        success=True,
        message=f"Retrieved {len(formatted)} call logs",
        data=formatted
    )


@router.websocket("/ws/{session_id}")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    """
    Real-time bidirectional WebSocket voice streaming endpoint.
    Accepts:
      - JSON text packets: {"type": "text", "data": "I want an appointment with cardiologist"}
      - Base64 or binary audio packets: {"type": "audio", "data": "<base64 wav>"}
    Streams back:
      - Transcripts
      - Spoken response text
      - Action triggers (DOCTORS_FOUND, BOOKING_CONFIRMED, APPOINTMENT_CANCELLED)
      - Synthesized audio chunks
    """
    await websocket.accept()
    logger.info(f"WebSocket voice connection opened for session {session_id}", extra={"session_id": session_id})

    # Prepare session state
    if session_id not in active_sessions:
        active_sessions[session_id] = VoiceSessionState(session_id=session_id)
    state = active_sessions[session_id]

    pipeline = VoicePipelineOrchestrator()

    # Send initial welcome greeting frame
    welcome_text = f"Hello! Welcome to {settings.HOSPITAL_NAME}. I am Maya, your AI receptionist. How can I assist you with doctor appointments or hospital services today?"
    try:
        # Synthesize audio greeting
        welcome_audio = await pipeline.tts.synthesize(welcome_text)
        welcome_audio_b64 = base64.b64encode(welcome_audio).decode("utf-8")

        await websocket.send_text(
            VoiceFrame(
                type="text",
                role="assistant",
                data=welcome_text,
                is_final=True
            ).model_dump_json()
        )
        await websocket.send_text(
            VoiceFrame(
                type="audio",
                role="assistant",
                data=welcome_audio_b64,
                format="wav",
                is_final=True
            ).model_dump_json()
        )
    except Exception as e:
        logger.error(f"Error sending welcome voice frame: {e}", exc_info=True)

    # Listen loop
    try:
        while True:
            message = await websocket.receive_text()
            try:
                frame_dict = json.loads(message)
                frame = VoiceFrame(**frame_dict)
            except Exception:
                # If raw text was sent
                frame = VoiceFrame(type="text", data=message)

            user_text = ""
            if frame.type == "text" and frame.data:
                user_text = frame.data.strip()
            elif frame.type == "audio" and frame.data:
                # Decode audio bytes and transcribe with STT
                try:
                    audio_bytes = base64.b64decode(frame.data)
                    user_text = await pipeline.stt.transcribe(audio_bytes)
                except Exception as e:
                    logger.error(f"STT transcription error: {e}")
                    user_text = "I would like to check doctor availability."

            elif frame.type == "control":
                if frame.data == "HANGUP":
                    break
                continue

            if user_text:
                # Process turn inside an isolated DB session
                async with AsyncSessionLocal() as session:
                    await pipeline.process_user_turn(session, state, websocket, user_text)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in voice session {session_id}: {e}", exc_info=True)
    finally:
        # Update call duration in DB
        duration = int(time.time() - state.start_time)
        try:
            async with AsyncSessionLocal() as session:
                call_res = await session.execute(select(CallLog).where(CallLog.session_id == session_id))
                call = call_res.scalars().first()
                if call:
                    call.status = "COMPLETED"
                    call.duration_seconds = duration
                    await session.commit()
        except Exception:
            pass

        if session_id in active_sessions:
            del active_sessions[session_id]
        logger.info(f"Closed voice session {session_id} (duration: {duration}s)")
