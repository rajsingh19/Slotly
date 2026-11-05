import re
import pytest
import asyncio
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.services.voice.agent.state_machine import (
    ConversationState,
    ConversationContext,
    DeterministicNLP,
    get_current_date_in_hospital_tz
)
from app.services.voice.agent.tools import (
    tool_registry,
    SearchDoctorsInput,
    GetDoctorDetailsInput,
    CheckAvailabilityInput,
    RegisterPatientInput,
    BookAppointmentInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput,
    GetHospitalInformationInput,
    RequestHumanHandoffInput
)
from app.services.voice.agent.receptionist_agent import receptionist_agent
from app.schemas.voice import VoiceFrame


# =====================================================================
# 1. Hindi Appointment Booking Test
# =====================================================================
@pytest.mark.asyncio
async def test_hindi_appointment_booking(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+919876543210"})
    session_id = session_res.json()["data"]["session_id"]

    # Turn 1: Patient asks in Hindi for skin doctor
    r1 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mujhe+skin+doctor+ko+dikhana+hai")
    reply1 = r1.json()["data"]["assistant_reply"]
    assert any(w in reply1.lower() for w in ["din", "appointment", "kal", "parson", "tarikh"])

    # Turn 2: Patient says "Kal"
    r2 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Kal")
    reply2 = r2.json()["data"]["assistant_reply"]
    assert "sunita patel" in reply2.lower() or "slot" in reply2.lower()

    # Turn 3: Patient picks time slot
    r3 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=11:00+AM")
    reply3 = r3.json()["data"]["assistant_reply"]
    assert any(w in reply3.lower() for w in ["naam", "phone", "number", "kiske"])

    # Turn 4: Patient provides details
    r4 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mera+naam+Rahul+Verma+hai+aur+phone+9876543210+hai")
    reply4 = r4.json()["data"]["assistant_reply"]
    assert any(w in reply4.lower() for w in ["confirm", "kya main", "kar doon"])

    # Turn 5: Patient confirms
    r5 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Haan+confirm+kar+do")
    reply5 = r5.json()["data"]["assistant_reply"]
    assert "apt-" in reply5.lower()
    assert any(w in reply5.lower() for w in ["badhai", "confirm", "book"])


# =====================================================================
# 2. English Appointment Booking Test
# =====================================================================
@pytest.mark.asyncio
async def test_english_appointment_booking(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    session_id = session_res.json()["data"]["session_id"]

    # Turn 1: Inquire for pediatric doctor
    r1 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=I+need+an+appointment+with+a+pediatrician")
    reply1 = r1.json()["data"]["assistant_reply"]
    assert "priya menon" in reply1.lower() or "what day" in reply1.lower() or "date" in reply1.lower()

    # Turn 2: Tomorrow
    r2 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Tomorrow")
    reply2 = r2.json()["data"]["assistant_reply"]
    assert "slots" in reply2.lower()

    # Turn 3: Time slot
    r3 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=14:00")
    reply3 = r3.json()["data"]["assistant_reply"]
    assert "name" in reply3.lower()

    # Turn 4: Name
    r4 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Patient+name+is+Alice+Cooper")
    reply4 = r4.json()["data"]["assistant_reply"]
    assert "shall i confirm" in reply4.lower() or "confirm" in reply4.lower()

    # Turn 5: Confirm
    r5 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Yes+please+confirm")
    reply5 = r5.json()["data"]["assistant_reply"]
    assert "apt-" in reply5.lower()
    assert "confirmed" in reply5.lower() or "booked" in reply5.lower()


# =====================================================================
# 3. Hinglish Appointment Booking Test
# =====================================================================
@pytest.mark.asyncio
async def test_hinglish_appointment_booking(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+919988776655"})
    session_id = session_res.json()["data"]["session_id"]

    # Turn 1
    r1 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mujhe+dil+ke+doctor+se+milna+hai")
    reply1 = r1.json()["data"]["assistant_reply"]
    assert "rajesh sharma" in reply1.lower() or "din" in reply1.lower() or "date" in reply1.lower()

    # Turn 2
    r2 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Kal")
    reply2 = r2.json()["data"]["assistant_reply"]
    assert "slots" in reply2.lower()

    # Turn 3
    r3 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=14:00+baje+wala+slot")
    reply3 = r3.json()["data"]["assistant_reply"]
    assert "naam" in reply3.lower() or "name" in reply3.lower()

    # Turn 4
    r4 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mera+naam+Vikas+Gupta+hai")
    reply4 = r4.json()["data"]["assistant_reply"]
    assert "confirm" in reply4.lower()

    # Turn 5
    r5 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Theek+hai+confirm+kardo")
    reply5 = r5.json()["data"]["assistant_reply"]
    assert "apt-" in reply5.lower()


# =====================================================================
# 4. Doctor Search Tool Test
# =====================================================================
@pytest.mark.asyncio
async def test_doctor_search_tool(db_session: AsyncSession):
    # Standard English search
    res = await tool_registry.search_doctors(db_session, SearchDoctorsInput(specialization="Dermatology"))
    assert res["status"] == "success"
    assert res["count"] >= 1
    assert "Sunita Patel" in res["doctors"][0]["name"]

    # Informal Hindi slang mapping: "chamdi" -> Dermatology
    res_hindi = await tool_registry.search_doctors(db_session, SearchDoctorsInput(specialization="chamdi"))
    assert res_hindi["status"] == "success"
    assert res_hindi["specialization"] == "Dermatology"


# =====================================================================
# 5. Availability Checking Tool Test
# =====================================================================
@pytest.mark.asyncio
async def test_availability_checking_tool(db_session: AsyncSession):
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    res = await tool_registry.check_availability(
        db_session, CheckAvailabilityInput(doctor_id=1, date=tomorrow_str)
    )
    assert res["status"] == "success"
    assert "available_slots" in res
    assert len(res["available_slots"]) > 0


# =====================================================================
# 6. Successful Booking Tool Test
# =====================================================================
@pytest.mark.asyncio
async def test_successful_booking_tool(db_session: AsyncSession):
    # Register patient first
    p_res = await tool_registry.register_patient(
        db_session, RegisterPatientInput(name="George Washington", phone_number="+15554443322")
    )
    patient_id = p_res["patient_id"]

    target_date = (date.today() + timedelta(days=4)).isoformat()
    b_res = await tool_registry.book_appointment(
        db_session, BookAppointmentInput(
            patient_id=patient_id,
            doctor_id=2,
            date=target_date,
            time="11:30"
        )
    )
    assert b_res["status"] == "booked"
    assert b_res["booking_reference"].startswith("APT-")
    assert b_res["date"] == target_date
    assert b_res["time"] == "11:30"


# =====================================================================
# 7. Booking Explicit Confirmation Test
# =====================================================================
@pytest.mark.asyncio
async def test_booking_explicit_confirmation_discipline(db_session: AsyncSession):
    ctx = ConversationContext(session_id="test-confirm-disc", caller_phone="+15559998888")
    ctx.specialization = "Cardiology"
    ctx.doctor_id = 1
    ctx.doctor_name = "Dr. Rajesh Sharma"
    ctx.appointment_date = date.today() + timedelta(days=5)
    ctx.appointment_time = "15:00"
    ctx.patient_id = 1
    ctx.patient_name = "Eleanor Vance"

    # When user has NOT confirmed yet
    reply, action_type, _ = await receptionist_agent.handle_turn(db_session, ctx, "I might want to check this")
    assert action_type == "CONFIRM_BOOKING_PROMPT"
    assert ctx.current_state == ConversationState.CONFIRM_BOOKING
    assert ctx.booking_reference is None  # NOT booked yet!

    # Now user confirms explicitly
    reply2, action_type2, payload2 = await receptionist_agent.handle_turn(db_session, ctx, "Yes, please confirm it now")
    assert action_type2 == "BOOKING_SUCCESS"
    assert ctx.current_state == ConversationState.BOOKING_SUCCESS
    assert ctx.booking_reference is not None  # Now booked!


# =====================================================================
# 8. Booking Cancellation Test
# =====================================================================
@pytest.mark.asyncio
async def test_booking_cancellation(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    session_id = session_res.json()["data"]["session_id"]

    # Book an appointment
    book_turn = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Yes+please+book+appointment+with+Dr.+Rajesh+Sharma+for+Thomas+Edison+at+14:00+on+{(date.today() + timedelta(days=3)).isoformat()}+phone+15558887766"
    )
    ref_match = re.search(r"APT-[\w-]+", book_turn.json()["data"]["assistant_reply"])
    assert ref_match is not None
    booking_ref = ref_match.group(0)

    # Cancel the appointment
    cancel_turn = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Please+cancel+my+appointment+{booking_ref}"
    )
    reply_cancel = cancel_turn.json()["data"]["assistant_reply"]
    assert "cancel" in reply_cancel.lower()


# =====================================================================
# 9. Appointment Rescheduling Test
# =====================================================================
@pytest.mark.asyncio
async def test_appointment_rescheduling(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    session_id = session_res.json()["data"]["session_id"]

    # Initial booking
    new_date = (date.today() + timedelta(days=6)).isoformat()
    book_turn = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Yes+please+book+appointment+with+Dr.+Rajesh+Sharma+for+Marie+Curie+at+10:30+on+{new_date}+phone+15554441111"
    )
    ref_match = re.search(r"APT-[\w-]+", book_turn.json()["data"]["assistant_reply"])
    assert ref_match is not None
    booking_ref = ref_match.group(0)

    # Reschedule
    resched_date = (date.today() + timedelta(days=7)).isoformat()
    resched_turn = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Please+reschedule+appointment+{booking_ref}+to+{resched_date}+at+14:30"
    )
    reply_resched = resched_turn.json()["data"]["assistant_reply"]
    assert "reschedule" in reply_resched.lower() or "14:30" in reply_resched


# =====================================================================
# 10. No Available Slots Test
# =====================================================================
@pytest.mark.asyncio
async def test_no_available_slots(db_session: AsyncSession):
    target_date = date.today() + timedelta(days=8)
    
    # Fill up all slots for Doctor 1 on target_date
    slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"]
    for s in slots:
        db_session.add(
            Appointment(
                patient_id=1,
                doctor_id=1,
                appointment_date=target_date,
                appointment_time=s,
                status="SCHEDULED",
                booking_reference=f"APT-FILL-{s.replace(':', '')}"
            )
        )
    await db_session.commit()

    ctx = ConversationContext(session_id="test-full-slots")
    ctx.specialization = "Cardiology"
    ctx.doctor_id = 1
    ctx.doctor_name = "Dr. Rajesh Sharma"
    ctx.appointment_date = target_date

    reply, action_type, payload = await receptionist_agent.handle_turn(db_session, ctx, "What slots are open?")
    assert action_type == "NO_SLOTS_AVAILABLE"
    assert "fully booked" in reply.lower() or "फुल" in reply or "slots full" in reply.lower()


# =====================================================================
# 11. Invalid Patient Details Test
# =====================================================================
@pytest.mark.asyncio
async def test_invalid_patient_details(db_session: AsyncSession):
    # Invalid short phone number handled safely by tool registry
    res = await tool_registry.execute(
        tool_name="register_patient",
        arguments={"name": "John Doe", "phone_number": "123"},
        db=db_session
    )
    assert res["status"] == "validation_error"
    assert "10-15 digits" in res["message"] or "validation" in res["message"].lower()


# =====================================================================
# 12. Duplicate Booking Prevention Test
# =====================================================================
@pytest.mark.asyncio
async def test_duplicate_booking_prevention(db_session: AsyncSession):
    target_date = (date.today() + timedelta(days=9)).isoformat()
    # Book first
    res1 = await tool_registry.book_appointment(
        db_session, BookAppointmentInput(
            patient_id=1, doctor_id=3, date=target_date, time="10:00"
        )
    )
    assert res1["status"] == "booked"

    # Try duplicate appointment for same patient at same date/time with another doctor
    res2 = await tool_registry.book_appointment(
        db_session, BookAppointmentInput(
            patient_id=1, doctor_id=4, date=target_date, time="10:00"
        )
    )
    assert res2["status"] == "conflict"
    assert "duplicate appointment" in res2["message"].lower()


# =====================================================================
# 13. Concurrent Booking Safety Test
# =====================================================================
@pytest.mark.asyncio
async def test_concurrent_booking_safety(client: AsyncClient):
    target_date = (date.today() + timedelta(days=10)).isoformat()
    p1 = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "15:30",
        "patient_name": "Racer One",
        "patient_phone": "+15551119999"
    }
    p2 = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "15:30",
        "patient_name": "Racer Two",
        "patient_phone": "+15552229999"
    }

    res_a, res_b = await asyncio.gather(
        client.post("/api/appointments", json=p1),
        client.post("/api/appointments", json=p2),
        return_exceptions=False
    )
    statuses = [res_a.status_code, res_b.status_code]
    assert 201 in statuses
    assert 409 in statuses


# =====================================================================
# 14. LLM Tool-Calling Failure Graceful Handling Test
# =====================================================================
@pytest.mark.asyncio
async def test_llm_tool_calling_failure_graceful_handling(db_session: AsyncSession):
    # Pass bad arguments to unknown tool
    res = await tool_registry.execute(
        tool_name="unknown_fictional_tool",
        arguments={"fake": 123},
        db=db_session
    )
    assert res["status"] == "error"
    assert "unknown tool" in res["message"].lower()

    # Pass invalid types to book_appointment tool
    res_bad_types = await tool_registry.execute(
        tool_name="book_appointment",
        arguments={"patient_id": "not-an-int", "doctor_id": -5, "date": "yesterday", "time": "none"},
        db=db_session
    )
    assert res_bad_types["status"] == "validation_error"


# =====================================================================
# 15. Patient Disconnect During Booking Test
# =====================================================================
def test_patient_disconnect_during_booking():
    test_client = TestClient(app)
    session_id = f"test-disconnect-{date.today().isoformat()}"

    with test_client.websocket_connect(f"/api/voice/ws/{session_id}") as ws:
        # Read welcome packet
        ws.receive_text()
        # Disconnect abruptly
        ws.close()

    # Verify session closed cleanly without leaking threads
    res = test_client.get("/api/voice/calls")
    assert res.status_code == 200


# =====================================================================
# 16. Human Handoff Test
# =====================================================================
@pytest.mark.asyncio
async def test_human_handoff(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    session_id = session_res.json()["data"]["session_id"]

    r = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Mujhe+kisi+insaan+se+baat+karni+hai"
    )
    reply = r.json()["data"]["assistant_reply"]
    assert any(w in reply.lower() for w in ["transfer", "connect", "staff", "line par"])


# =====================================================================
# 17. Emergency Handling Test
# =====================================================================
@pytest.mark.asyncio
async def test_emergency_handling(client: AsyncClient):
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    session_id = session_res.json()["data"]["session_id"]

    # Hindi / Hinglish emergency
    r_hindi = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Mere+seene+mein+tez+dard+hai+aur+saans+phool+rahi+hai"
    )
    reply_hindi = r_hindi.json()["data"]["assistant_reply"]
    assert any(w in reply_hindi for w in ["इमरजेंसी", "108", "इमरजेंसी वार्ड", "Emergency", "emergency"])

    # English emergency
    r_eng = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=My+father+is+having+chest+pain+and+heavy+bleeding"
    )
    reply_eng = r_eng.json()["data"]["assistant_reply"]
    assert "emergency" in reply_eng.lower()
    assert settings.HOSPITAL_EMERGENCY_PHONE in reply_eng


# =====================================================================
# 18. Session Context Isolation Test
# =====================================================================
@pytest.mark.asyncio
async def test_session_context_isolation(client: AsyncClient):
    # Session 1 for Dr. Sunita Patel (Dermatology)
    s1_res = await client.post("/api/voice/session", json={"caller_phone": "+15551111111"})
    id1 = s1_res.json()["data"]["session_id"]
    await client.post(f"/api/voice/simulate-turn?session_id={id1}&message=Mujhe+skin+doctor+chahiye")

    # Session 2 for Dr. Rajesh Sharma (Cardiology)
    s2_res = await client.post("/api/voice/session", json={"caller_phone": "+15552222222"})
    id2 = s2_res.json()["data"]["session_id"]
    await client.post(f"/api/voice/simulate-turn?session_id={id2}&message=I+want+a+heart+doctor")

    # Turn 2 on Session 1 should still be about Dermatology
    t1_check = await client.post(f"/api/voice/simulate-turn?session_id={id1}&message=Kal")
    assert "sunita patel" in t1_check.json()["data"]["assistant_reply"].lower()

    # Turn 2 on Session 2 should still be about Cardiology
    t2_check = await client.post(f"/api/voice/simulate-turn?session_id={id2}&message=Tomorrow")
    assert "rajesh sharma" in t2_check.json()["data"]["assistant_reply"].lower()
