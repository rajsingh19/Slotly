import base64
import time
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import WebSocket

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.voice import VoiceFrame
from app.schemas.appointment import AppointmentCreate
from app.services.voice.base import BaseSTTService, BaseTTSService, BaseLLMService
from app.services.voice.stt_adapter import get_stt_service
from app.services.voice.tts_adapter import get_tts_service
from app.services.voice.llm_adapter import get_llm_service, RECEPTIONIST_TOOLS, HOSPITAL_SYSTEM_PROMPT
from app.services.hospital_service import hospital_service
from app.models.call_log import CallLog, CallTranscript

logger = get_logger(__name__)


class VoiceSessionState:
    """
    Maintains multi-turn context and pending slot booking state during a call.
    """
    def __init__(self, session_id: str, caller_phone: Optional[str] = None):
        self.session_id = session_id
        self.caller_phone = caller_phone or "+1-555-0100"
        self.caller_name: Optional[str] = None
        self.conversation_history: List[Dict[str, str]] = []
        self.start_time = time.time()
        self.pending_doctor_id: Optional[int] = None
        self.pending_slot_id: Optional[int] = None
        self.pending_specialty: Optional[str] = None


class VoicePipelineOrchestrator:
    """
    Pipecat-inspired streaming voice pipeline orchestrator.
    Handles audio chunk ingestion, speech recognition, intent execution,
    tool execution, speech synthesis, and real-time streaming back to the client.
    """

    def __init__(
        self,
        stt_service: Optional[BaseSTTService] = None,
        tts_service: Optional[BaseTTSService] = None,
        llm_service: Optional[BaseLLMService] = None,
    ):
        self.stt = stt_service or get_stt_service()
        self.tts = tts_service or get_tts_service()
        self.llm = llm_service or get_llm_service()

    async def initialize_call(self, db: AsyncSession, session_id: str, caller_phone: Optional[str] = None) -> CallLog:
        """
        Record start of call in CallLog table or retrieve existing.
        """
        stmt = select(CallLog).where(CallLog.session_id == session_id)
        result = await db.execute(stmt)
        existing = result.scalars().first()
        if existing:
            return existing

        call_log = CallLog(
            session_id=session_id,
            caller_phone=caller_phone,
            status="ACTIVE",
            intent="INQUIRY",
            duration_seconds=0,
            summary="Call initiated",
        )
        db.add(call_log)
        await db.commit()
        await db.refresh(call_log)
        return call_log

    async def execute_tool(
        self,
        db: AsyncSession,
        state: VoiceSessionState,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute business domain tools called by the voice dialogue agent.
        """
        logger.info(f"Executing tool {tool_name} with args {arguments}", extra={"action": "TOOL_INVOCATION"})

        if tool_name == "check_doctor_availability":
            specialty = arguments.get("specialty")
            slots = await hospital_service.get_available_slots(db, specialty=specialty)
            if not slots:
                return {
                    "status": "none_found",
                    "message": f"No available appointment slots found for {specialty or 'requested doctors'}.",
                    "available_slots": []
                }
            
            # Format top 3 slots for voice
            top_slots = slots[:3]
            state.pending_doctor_id = top_slots[0].doctor_id
            state.pending_slot_id = top_slots[0].id

            formatted = [
                {
                    "slot_id": s.id,
                    "doctor_name": s.doctor.name,
                    "specialty": s.doctor.specialty,
                    "date": s.slot_date.strftime("%A, %B %d"),
                    "time": f"{s.start_time} to {s.end_time}",
                    "fee": s.doctor.consultation_fee
                }
                for s in top_slots
            ]
            return {
                "status": "success",
                "available_slots": formatted,
                "first_slot_id": top_slots[0].id,
                "first_doctor_id": top_slots[0].doctor_id
            }

        elif tool_name == "book_appointment":
            patient_name = arguments.get("patient_name") or state.caller_name or "Guest Patient"
            patient_phone = arguments.get("patient_phone") or state.caller_phone or "+1-555-0100"
            doctor_id = arguments.get("doctor_id") or state.pending_doctor_id
            slot_id = arguments.get("slot_id") or state.pending_slot_id

            if not doctor_id or not slot_id:
                # Fallback to first available slot if not specified
                slots = await hospital_service.get_available_slots(db)
                if slots:
                    doctor_id = slots[0].doctor_id
                    slot_id = slots[0].id

            if not doctor_id or not slot_id:
                return {"status": "error", "message": "Could not identify doctor or slot to book."}

            apt_data = AppointmentCreate(
                patient_name=patient_name,
                patient_phone=patient_phone,
                doctor_id=doctor_id,
                slot_id=slot_id,
                reason_for_visit=arguments.get("reason_for_visit", "General Consultation")
            )
            appointment = await hospital_service.book_appointment(db, apt_data)
            return {
                "status": "booked",
                "appointment_number": appointment.appointment_number,
                "doctor_name": appointment.doctor.name if appointment.doctor else "Doctor",
                "date": appointment.appointment_date.isoformat(),
                "time": appointment.appointment_time,
                "patient_name": appointment.patient_name
            }

        elif tool_name == "reschedule_appointment":
            identifier = arguments.get("appointment_identifier", "")
            new_slot_id = arguments.get("new_slot_id") or state.pending_slot_id
            if not new_slot_id:
                slots = await hospital_service.get_available_slots(db)
                if slots:
                    new_slot_id = slots[0].id
            
            if not new_slot_id:
                return {"status": "error", "message": "No alternative slots available to reschedule."}

            appointment = await hospital_service.reschedule_appointment(
                db,
                appointment_identifier=identifier,
                new_slot_id=new_slot_id,
                reason=arguments.get("reason", "Patient request")
            )
            return {
                "status": "rescheduled",
                "appointment_number": appointment.appointment_number,
                "new_date": appointment.appointment_date.isoformat(),
                "new_time": appointment.appointment_time
            }

        elif tool_name == "cancel_appointment":
            identifier = arguments.get("appointment_identifier", "")
            appointment = await hospital_service.cancel_appointment(
                db,
                appointment_identifier=identifier,
                reason=arguments.get("reason", "Cancelled by patient via voice")
            )
            return {
                "status": "cancelled",
                "appointment_number": appointment.appointment_number
            }

        elif tool_name == "get_hospital_info":
            query = arguments.get("query", "")
            faqs = await hospital_service.list_faqs(db, query=query)
            if faqs:
                return {"status": "found", "info": faqs[0].answer}
            return {
                "status": "general",
                "info": f"{settings.HOSPITAL_NAME} visiting hours are {settings.HOSPITAL_VISITING_HOURS}. Emergency ward is open 24/7."
            }

        return {"status": "unknown_tool"}

    async def process_user_turn(
        self,
        db: AsyncSession,
        state: VoiceSessionState,
        websocket: Optional[WebSocket],
        user_text: str
    ) -> str:
        """
        Process a transcribed user turn through dialogue management, tools, and speech synthesis.
        """
        t0 = time.time()
        state.conversation_history.append({"role": "user", "content": user_text})

        # Save transcript turn to DB
        call_log = await self.initialize_call(db, state.session_id, state.caller_phone)
        user_transcript = CallTranscript(
            call_log_id=call_log.id,
            speaker="user",
            message=user_text,
            latency_ms=0.0
        )
        db.add(user_transcript)
        await db.commit()

        # Send user text recognition event back to frontend
        if websocket:
            await websocket.send_text(
                VoiceFrame(
                    type="text",
                    role="user",
                    data=user_text,
                    is_final=True
                ).model_dump_json()
            )

        # Generate LLM response & tool calls
        llm_start = time.time()
        llm_response = await self.llm.generate_response(
            messages=state.conversation_history,
            system_prompt=HOSPITAL_SYSTEM_PROMPT,
            available_tools=RECEPTIONIST_TOOLS
        )
        llm_latency_ms = (time.time() - llm_start) * 1000

        tool_calls = llm_response.get("tool_calls")
        reply_content = llm_response.get("content", "")
        action_type = None
        action_payload = None

        if tool_calls:
            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name")
                args_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {}

                tool_result = await self.execute_tool(db, state, func_name, args)

                # Formulate natural spoken response based on tool result
                if func_name == "check_doctor_availability" and tool_result.get("available_slots"):
                    slots = tool_result["available_slots"]
                    first = slots[0]
                    reply_content = f"We have {first['doctor_name']}, specialist in {first['specialty']}, available on {first['date']} at {first['time']}. Would you like me to book this for you?"
                    action_type = "DOCTORS_FOUND"
                    action_payload = tool_result
                elif func_name == "book_appointment" and tool_result.get("status") == "booked":
                    reply_content = f"Your appointment has been successfully booked with {tool_result['doctor_name']} for {tool_result['date']} at {tool_result['time']}. Your appointment reference is {tool_result['appointment_number']}. A confirmation message has been recorded."
                    action_type = "BOOKING_CONFIRMED"
                    action_payload = tool_result
                elif func_name == "reschedule_appointment" and tool_result.get("status") == "rescheduled":
                    reply_content = f"Your appointment {tool_result['appointment_number']} has been rescheduled to {tool_result['new_date']} at {tool_result['new_time']}."
                    action_type = "APPOINTMENT_RESCHEDULED"
                    action_payload = tool_result
                elif func_name == "cancel_appointment" and tool_result.get("status") == "cancelled":
                    reply_content = f"Your appointment {tool_result['appointment_number']} has been cancelled. Please let me know if you need to schedule another visit."
                    action_type = "APPOINTMENT_CANCELLED"
                    action_payload = tool_result
                elif func_name == "get_hospital_info" and tool_result.get("info"):
                    reply_content = tool_result["info"]

        # Append assistant turn to history
        state.conversation_history.append({"role": "assistant", "content": reply_content})

        # Synthesize audio with TTS
        tts_start = time.time()
        audio_bytes = await self.tts.synthesize(reply_content)
        tts_latency_ms = (time.time() - tts_start) * 1000
        total_latency_ms = (time.time() - t0) * 1000

        # Persist assistant turn to DB
        assistant_transcript = CallTranscript(
            call_log_id=call_log.id,
            speaker="assistant",
            message=reply_content,
            latency_ms=total_latency_ms
        )
        db.add(assistant_transcript)
        await db.commit()

        # Stream text, action, and audio frames to WebSocket
        if websocket:
            # 1. Spoken text frame
            await websocket.send_text(
                VoiceFrame(
                    type="text",
                    role="assistant",
                    data=reply_content,
                    latency_ms=total_latency_ms,
                    action_type=action_type,
                    action_payload=action_payload,
                    is_final=True
                ).model_dump_json()
            )

            # 2. Audio frame (base64 encoded WAV/MP3)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            await websocket.send_text(
                VoiceFrame(
                    type="audio",
                    role="assistant",
                    data=audio_b64,
                    format="wav",
                    sample_rate=16000,
                    latency_ms=tts_latency_ms,
                    is_final=True
                ).model_dump_json()
            )

        logger.info(
            f"Voice turn completed in {total_latency_ms:.1f}ms (LLM: {llm_latency_ms:.1f}ms, TTS: {tts_latency_ms:.1f}ms)",
            extra={"action": "TURN_COMPLETE", "latency_ms": total_latency_ms}
        )
        return reply_content


voice_orchestrator = VoicePipelineOrchestrator()
