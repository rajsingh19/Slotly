import re
import time
import json
import base64
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import WebSocket, HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.voice import VoiceFrame
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.models.call_session import CallSession, CallEvent
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.repositories.hospital_repo import HospitalRepository
from app.repositories.doctor_repo import DoctorRepository
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.services.voice.base import BaseSTTService, BaseTTSService, BaseLLMService
from app.services.voice.stt_adapter import get_stt_service
from app.services.voice.tts_adapter import get_tts_service
from app.services.voice.llm_adapter import get_llm_service, RECEPTIONIST_TOOLS, HOSPITAL_SYSTEM_PROMPT

logger = get_logger(__name__)


class VoiceSessionState:
    """
    Maintains multi-turn conversation context, caller information,
    and pending appointment slots during a voice interaction.
    """
    def __init__(self, session_id: str, caller_phone: Optional[str] = None):
        self.session_id = session_id
        self.caller_phone = caller_phone or "+15551234567"
        self.caller_name: Optional[str] = None
        self.conversation_history: List[Dict[str, str]] = []
        self.start_time = time.time()
        self.call_session_db_id: Optional[int] = None
        self.call_log_db_id: Optional[int] = None
        self.pending_doctor_id: Optional[int] = None
        self.pending_doctor_name: Optional[str] = None
        self.pending_specialty: Optional[str] = None
        self.pending_date: Optional[str] = None
        self.pending_time: Optional[str] = None


class VoicePipelineOrchestrator:
    """
    Pipecat-inspired streaming voice pipeline orchestrator.
    Handles:
    - Audio ingestion & transcription (STT)
    - Dialogue management & intent understanding (LLM)
    - Domain tool execution via Service Layer (Doctor, Appointment, Call Services)
    - Speech synthesis with sentence-boundary streaming (TTS)
    - Real-time bidirectional WebSocket transport
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

    async def initialize_call(
        self,
        db: AsyncSession,
        state_or_session_id: Union[VoiceSessionState, str],
        caller_phone: Optional[str] = None
    ) -> CallSession:
        """
        Record start of call in CallSession and CallEvent tables.
        Also maintains backwards compatibility with CallLog.
        """
        if isinstance(state_or_session_id, VoiceSessionState):
            state = state_or_session_id
        else:
            state = VoiceSessionState(session_id=state_or_session_id, caller_phone=caller_phone)

        # 1. Fetch or create CallSession
        if state.call_session_db_id:
            stmt = select(CallSession).where(CallSession.id == state.call_session_db_id)
            res = await db.execute(stmt)
            call_sess = res.scalars().first()
            if call_sess:
                return call_sess

        call_sess = CallSession(
            caller_number=state.caller_phone,
            call_direction="INBOUND",
            status="ACTIVE",
            transcript="",
            duration_seconds=0,
            estimated_cost=0.0,
        )
        db.add(call_sess)
        await db.flush()
        state.call_session_db_id = call_sess.id

        # Record initial connection event
        connect_event = CallEvent(
            call_session_id=call_sess.id,
            event_type="CALL_CONNECTED",
            event_data=json.dumps({"session_id": state.session_id, "caller_number": state.caller_phone}),
        )
        db.add(connect_event)
        await db.flush()

        return call_sess

    async def execute_tool(
        self,
        db: AsyncSession,
        state: VoiceSessionState,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute business domain tools called by the voice dialogue agent.
        Never executes raw SQL — delegates cleanly to Service and Repository layers.
        """
        logger.info(f"Executing voice tool: {tool_name} with arguments {arguments}", extra={"action": "TOOL_INVOCATION"})

        doctor_service = DoctorService(db)
        appointment_service = AppointmentService(db)
        hospital_repo = HospitalRepository(db)

        # 1. Check Doctor Availability
        if tool_name == "check_doctor_availability":
            specialty = arguments.get("specialty")
            doctor_name = arguments.get("doctor_name")
            date_arg = arguments.get("date")

            target_date = date.today() + timedelta(days=1)
            if date_arg:
                try:
                    parsed_date = date.fromisoformat(date_arg)
                    if parsed_date >= date.today():
                        target_date = parsed_date
                except Exception:
                    pass

            # Resolve doctors by specialty or all active
            SPEC_MAP = {
                "cardiologist": "Cardiology",
                "cardiology": "Cardiology",
                "orthopedic": "Orthopedics",
                "orthopedics": "Orthopedics",
                "pediatrician": "Pediatrics",
                "pediatrics": "Pediatrics",
                "neurologist": "Neurology",
                "neurology": "Neurology",
                "dermatologist": "Dermatology",
                "dermatology": "Dermatology",
                "general physician": "General Medicine",
                "general medicine": "General Medicine",
            }
            if specialty:
                search_spec = SPEC_MAP.get(specialty.lower().strip(), specialty)
                doc_page = await doctor_service.list_doctors(specialization=search_spec, is_active=True, page=1, size=5)
                doctors = doc_page.items
            else:
                doc_page = await doctor_service.list_doctors(is_active=True, page=1, size=5)
                doctors = doc_page.items

            if not doctors:
                return {
                    "status": "none_found",
                    "message": f"No active doctors found for {specialty or 'the requested criteria'}.",
                    "available_slots": []
                }

            # Gather availability for matched doctors
            matched_availability = []
            for doc in doctors[:3]:
                doc_avail = await doctor_service.get_availability(doctor_id=doc.id, target_date=target_date)
                for da in doc_avail:
                    avail_slots = [s.time for s in da.slots if s.is_available]
                    if avail_slots:
                        matched_availability.append({
                            "doctor_id": da.doctor_id,
                            "doctor_name": da.doctor_name,
                            "specialty": da.specialization,
                            "date": da.date.isoformat(),
                            "slots": avail_slots,
                            "first_slot": avail_slots[0]
                        })

            if not matched_availability:
                return {
                    "status": "fully_booked",
                    "message": f"All doctors in {specialty or 'this department'} are fully booked on {target_date.isoformat()}.",
                    "available_slots": []
                }

            top_doc = matched_availability[0]
            state.pending_doctor_id = top_doc["doctor_id"]
            state.pending_doctor_name = top_doc["doctor_name"]
            state.pending_specialty = top_doc["specialty"]
            state.pending_date = top_doc["date"]
            state.pending_time = top_doc["first_slot"]

            return {
                "status": "success",
                "doctor_id": top_doc["doctor_id"],
                "doctor_name": top_doc["doctor_name"],
                "specialty": top_doc["specialty"],
                "date": top_doc["date"],
                "available_slots": top_doc["slots"],
                "first_slot": top_doc["first_slot"]
            }

        # 2. Book Appointment
        elif tool_name == "book_appointment":
            patient_name = arguments.get("patient_name") or state.caller_name or "Valued Patient"
            patient_phone = arguments.get("patient_phone") or state.caller_phone or "+15551234567"
            
            doctor_id = arguments.get("doctor_id") or state.pending_doctor_id
            appointment_date_str = arguments.get("date") or arguments.get("appointment_date") or state.pending_date
            appointment_time = arguments.get("time") or arguments.get("appointment_time") or state.pending_time or "10:00"

            # Parse date or default to tomorrow
            target_date = date.today() + timedelta(days=1)
            if appointment_date_str:
                try:
                    parsed_date = date.fromisoformat(appointment_date_str)
                    if parsed_date >= date.today():
                        target_date = parsed_date
                except Exception:
                    pass

            if not doctor_id:
                # Fallback to first active doctor
                active_docs = await DoctorRepository(db).get_all_active()
                if active_docs:
                    doctor_id = active_docs[0].id
                else:
                    return {"status": "error", "message": "No available doctors found to book."}

            try:
                apt_data = AppointmentCreate(
                    doctor_id=doctor_id,
                    appointment_date=target_date,
                    appointment_time=appointment_time,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    patient_email=arguments.get("patient_email")
                )
                apt = await appointment_service.create_appointment(apt_data)

                # Record event in CallSession
                if state.call_session_db_id:
                    event = CallEvent(
                        call_session_id=state.call_session_db_id,
                        event_type="APPOINTMENT_BOOKED",
                        event_data=json.dumps({
                            "booking_reference": apt.booking_reference,
                            "doctor_name": apt.doctor.name if apt.doctor else "Doctor",
                            "date": str(apt.appointment_date),
                            "time": apt.appointment_time
                        })
                    )
                    db.add(event)
                    await db.commit()

                return {
                    "status": "booked",
                    "appointment_number": apt.booking_reference,
                    "doctor_name": apt.doctor.name if apt.doctor else "Doctor",
                    "date": apt.appointment_date.isoformat(),
                    "time": apt.appointment_time,
                    "patient_name": apt.patient.name if apt.patient else patient_name
                }
            except HTTPException as he:
                return {"status": "error", "message": he.detail}
            except Exception as e:
                logger.error(f"Error booking appointment via voice: {e}", exc_info=True)
                return {"status": "error", "message": "Failed to complete appointment booking."}

        # 3. Reschedule Appointment
        elif tool_name == "reschedule_appointment":
            identifier = arguments.get("appointment_identifier", "").strip() or state.caller_phone
            new_date_str = arguments.get("new_date") or state.pending_date
            new_time = arguments.get("new_time") or arguments.get("appointment_time") or "11:00"

            target_date = date.today() + timedelta(days=2)
            if new_date_str:
                try:
                    parsed_date = date.fromisoformat(new_date_str)
                    if parsed_date >= date.today():
                        target_date = parsed_date
                except Exception:
                    pass

            apt = await appointment_service.find_appointment_by_ref_or_phone(identifier)
            if not apt:
                return {
                    "status": "not_found",
                    "message": f"Could not find an active appointment for '{identifier}'."
                }

            try:
                updated = await appointment_service.update_appointment(
                    apt.id,
                    AppointmentUpdate(
                        appointment_date=target_date,
                        appointment_time=new_time,
                        status="RESCHEDULED"
                    )
                )

                if state.call_session_db_id:
                    event = CallEvent(
                        call_session_id=state.call_session_db_id,
                        event_type="APPOINTMENT_RESCHEDULED",
                        event_data=json.dumps({
                            "booking_reference": updated.booking_reference,
                            "new_date": str(updated.appointment_date),
                            "new_time": updated.appointment_time
                        })
                    )
                    db.add(event)
                    await db.commit()

                return {
                    "status": "rescheduled",
                    "appointment_number": updated.booking_reference,
                    "doctor_name": updated.doctor.name if updated.doctor else "Doctor",
                    "new_date": updated.appointment_date.isoformat(),
                    "new_time": updated.appointment_time
                }
            except HTTPException as he:
                return {"status": "error", "message": he.detail}
            except Exception as e:
                return {"status": "error", "message": f"Rescheduling failed: {str(e)}"}

        # 4. Cancel Appointment
        elif tool_name == "cancel_appointment":
            identifier = arguments.get("appointment_identifier", "").strip() or state.caller_phone
            apt = await appointment_service.find_appointment_by_ref_or_phone(identifier)
            if not apt:
                return {
                    "status": "not_found",
                    "message": f"No active appointment found for '{identifier}' to cancel."
                }

            try:
                result = await appointment_service.delete_appointment(apt.id)

                if state.call_session_db_id:
                    event = CallEvent(
                        call_session_id=state.call_session_db_id,
                        event_type="APPOINTMENT_CANCELLED",
                        event_data=json.dumps({"booking_reference": apt.booking_reference})
                    )
                    db.add(event)
                    await db.commit()

                return {
                    "status": "cancelled",
                    "appointment_number": apt.booking_reference,
                    "message": result.get("message")
                }
            except HTTPException as he:
                return {"status": "error", "message": he.detail}

        # 5. Hospital Info & FAQs
        elif tool_name == "get_hospital_info":
            hospital = await hospital_repo.get_first()
            hospital_name = hospital.name if hospital else settings.HOSPITAL_NAME
            contact_number = hospital.contact_number if hospital else settings.HOSPITAL_PHONE
            address = hospital.address if hospital else settings.HOSPITAL_ADDRESS

            return {
                "status": "found",
                "hospital_name": hospital_name,
                "address": address,
                "contact_number": contact_number,
                "visiting_hours": settings.HOSPITAL_VISITING_HOURS,
                "emergency_phone": settings.HOSPITAL_EMERGENCY_PHONE
            }

        return {"status": "unknown_tool", "tool_name": tool_name}

    async def process_user_turn(
        self,
        db: AsyncSession,
        state: VoiceSessionState,
        websocket: Optional[WebSocket],
        user_text: str
    ) -> str:
        """
        Process a single spoken user turn:
        1. Transcript ingestion & persistence
        2. Dialogue management & function tool execution
        3. Spoken response synthesis with sentence-boundary streaming
        4. Real-time WebSocket packet transmission
        """
        t0 = time.time()
        state.conversation_history.append({"role": "user", "content": user_text})

        # Ensure call session initialized
        call_sess = await self.initialize_call(db, state)

        # Log SPEECH_RECOGNIZED event
        user_event = CallEvent(
            call_session_id=call_sess.id,
            event_type="SPEECH_RECOGNIZED",
            event_data=json.dumps({"user_text": user_text}),
        )
        db.add(user_event)
        await db.flush()

        # Send user text recognition event to WebSocket client
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
                if func_name == "check_doctor_availability":
                    if tool_result.get("status") == "success":
                        reply_content = f"We have {tool_result['doctor_name']}, specialist in {tool_result['specialty']}, available on {tool_result['date']} at {tool_result['first_slot']}. Would you like me to book this for you?"
                        action_type = "DOCTORS_FOUND"
                        action_payload = tool_result
                    else:
                        reply_content = tool_result.get("message", "No matching doctors or slots found.")

                elif func_name == "book_appointment":
                    if tool_result.get("status") == "booked":
                        reply_content = f"Your appointment has been successfully booked with {tool_result['doctor_name']} for {tool_result['date']} at {tool_result['time']}. Your booking reference is {tool_result['appointment_number']}."
                        action_type = "BOOKING_CONFIRMED"
                        action_payload = tool_result
                    else:
                        reply_content = f"I was unable to complete the booking. {tool_result.get('message', 'Please select another slot.')}"

                elif func_name == "reschedule_appointment":
                    if tool_result.get("status") == "rescheduled":
                        reply_content = f"Your appointment {tool_result['appointment_number']} has been successfully rescheduled to {tool_result['new_date']} at {tool_result['new_time']}."
                        action_type = "APPOINTMENT_RESCHEDULED"
                        action_payload = tool_result
                    else:
                        reply_content = f"I could not reschedule your appointment. {tool_result.get('message', '')}"

                elif func_name == "cancel_appointment":
                    if tool_result.get("status") == "cancelled":
                        reply_content = f"Your appointment {tool_result['appointment_number']} has been cancelled. Please let me know if you would like to book a different time."
                        action_type = "APPOINTMENT_CANCELLED"
                        action_payload = tool_result
                    else:
                        reply_content = f"I could not cancel the appointment. {tool_result.get('message', '')}"

                elif func_name == "get_hospital_info":
                    reply_content = f"{tool_result.get('hospital_name', 'Our hospital')} is located at {tool_result.get('address')}. Visiting hours are {tool_result.get('visiting_hours')}. For emergencies, call {tool_result.get('emergency_phone')}."

        # Append assistant turn to history
        state.conversation_history.append({"role": "assistant", "content": reply_content})

        total_latency_ms = (time.time() - t0) * 1000

        # Persist conversation turn into CallSession transcript
        call_sess.transcript = (call_sess.transcript or "") + f"User: {user_text}\nAssistant: {reply_content}\n"
        assistant_event = CallEvent(
            call_session_id=call_sess.id,
            event_type="SPEECH_SYNTHESIZED",
            event_data=json.dumps({"reply_content": reply_content, "latency_ms": total_latency_ms}),
        )
        db.add(assistant_event)
        await db.commit()

        # Sentence-boundary streaming over WebSocket
        if websocket:
            # 1. Send complete text frame with action metadata
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

            # 2. Split response into sentences for streaming audio playback
            sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', reply_content) if s.strip()]
            if not sentences:
                sentences = [reply_content]

            for i, sentence in enumerate(sentences):
                is_last_sentence = (i == len(sentences) - 1)
                chunk_audio = await self.tts.synthesize(sentence)
                chunk_b64 = base64.b64encode(chunk_audio).decode("utf-8")
                await websocket.send_text(
                    VoiceFrame(
                        type="audio",
                        role="assistant",
                        data=chunk_b64,
                        format="wav",
                        sample_rate=16000,
                        is_final=is_last_sentence
                    ).model_dump_json()
                )

        logger.info(
            f"Voice turn completed in {total_latency_ms:.1f}ms (LLM: {llm_latency_ms:.1f}ms)",
            extra={"action": "TURN_COMPLETE", "latency_ms": total_latency_ms}
        )
        return reply_content


voice_orchestrator = VoicePipelineOrchestrator()
