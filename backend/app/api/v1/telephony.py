from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.api.deps import get_database_session, get_voice_pipeline
from app.services.voice.pipeline import VoicePipelineOrchestrator, VoiceSessionState
from app.services.telephony.plivo_service import plivo_service

logger = get_logger(__name__)

router = APIRouter(prefix="/telephony/plivo", tags=["Telephony (Plivo)"])


@router.post("/answer")
async def plivo_answer_call(request: Request):
    """
    Plivo Answer URL callback: greeted when an incoming call connects.
    """
    form_data = await request.form()
    call_uuid = form_data.get("CallUUID", "unknown_call")
    from_number = form_data.get("From", "unknown_caller")

    logger.info(f"Incoming Plivo phone call from {from_number} (UUID: {call_uuid})", extra={"action": "INCOMING_CALL"})

    xml = plivo_service.generate_welcome_xml(callback_url=str(request.url))
    return Response(content=xml, media_type="application/xml")


@router.post("/event")
async def plivo_speech_event(
    request: Request,
    db: AsyncSession = Depends(get_database_session),
    pipeline: VoicePipelineOrchestrator = Depends(get_voice_pipeline),
):
    """
    Plivo Speech recognition result callback.
    Receives caller transcribed speech, executes hospital workflow, and speaks back.
    """
    form_data = await request.form()
    speech_result = form_data.get("Speech", "")
    call_uuid = form_data.get("CallUUID", "unknown_call")
    from_number = form_data.get("From", "unknown_caller")

    logger.info(f"Plivo speech recognized: '{speech_result}' for call {call_uuid}")

    if not speech_result:
        # Prompt caller again if silence
        xml = plivo_service.generate_reply_xml(
            "I didn't quite catch that. You can ask to book an appointment with a doctor, or ask about hospital visiting hours."
        )
        return Response(content=xml, media_type="application/xml")

    # Process caller query through pipeline
    state = VoiceSessionState(session_id=call_uuid, caller_phone=from_number)
    reply_text = await pipeline.process_user_turn(db, state, websocket=None, user_text=speech_result)

    xml = plivo_service.generate_reply_xml(reply_text, continue_conversation=True)
    return Response(content=xml, media_type="application/xml")
