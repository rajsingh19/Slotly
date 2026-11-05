import pytest
from app.services.voice.tts_adapter import MockTTSService
from app.services.voice.stt_adapter import MockSTTService


import re
import pytest
from httpx import AsyncClient
from app.services.voice.tts_adapter import MockTTSService
from app.services.voice.stt_adapter import MockSTTService


@pytest.mark.asyncio
async def test_mock_voice_adapters():
    stt = MockSTTService()
    transcript = await stt.transcribe(b"SIMULATED_SPEECH: I need to see Dr. Sharma")
    assert transcript == "I need to see Dr. Sharma"

    tts = MockTTSService()
    wav_bytes = await tts.synthesize("Your appointment is confirmed.")
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_voice_session_lifecycle(client: AsyncClient):
    # 1. Create a new voice session
    session_res = await client.post("/api/voice/session", json={"caller_phone": "+15551234567"})
    assert session_res.status_code == 200
    data = session_res.json()["data"]
    assert "session_id" in data
    assert "ws_url" in data
    assert "welcome_message" in data
    session_id = data["session_id"]

    # 2. Simulate dialogue turn: check doctor availability
    turn1_res = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Do+you+have+a+cardiologist+available+tomorrow"
    )
    assert turn1_res.status_code == 200
    turn1_data = turn1_res.json()["data"]
    assert "assistant_reply" in turn1_data
    assert "available" in turn1_data["assistant_reply"].lower()

    # 3. Simulate dialogue turn: book appointment
    turn2_res = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Yes+please+book+appointment+for+Eleanor+Vance+at+14:00+phone+15557778888"
    )
    assert turn2_res.status_code == 200
    turn2_data = turn2_res.json()["data"]
    reply2 = turn2_data["assistant_reply"]
    assert "booked" in reply2.lower()
    
    # Extract generated booking reference
    match = re.search(r"APT-[\w-]+", reply2)
    assert match is not None, f"Expected booking reference in reply: {reply2}"
    booking_ref = match.group(0)

    # 4. Simulate dialogue turn: cancel appointment
    turn3_res = await client.post(
        f"/api/voice/simulate-turn?session_id={session_id}&message=Please+cancel+my+appointment+{booking_ref}"
    )
    assert turn3_res.status_code == 200
    turn3_data = turn3_res.json()["data"]
    assert "cancelled" in turn3_data["assistant_reply"].lower()

    # 5. Verify call sessions endpoint lists this voice call
    calls_res = await client.get("/api/voice/calls")
    assert calls_res.status_code == 200
    calls_data = calls_res.json()["data"]
    assert len(calls_data) >= 1


@pytest.mark.asyncio
async def test_telephony_plivo_endpoints(client: AsyncClient):
    # 1. Answer URL callback returns XML
    ans_res = await client.post(
        "/api/telephony/plivo/answer",
        data={"CallUUID": "plivo-call-123", "From": "+15558889999"}
    )
    assert ans_res.status_code == 200
    assert "xml" in ans_res.headers.get("content-type", "").lower()
    assert "<Response>" in ans_res.text

    # 2. Event speech callback returns XML
    event_res = await client.post(
        "/api/telephony/plivo/event",
        data={
            "CallUUID": "plivo-call-123",
            "From": "+15558889999",
            "Speech": "What are your visiting hours?"
        }
    )
    assert event_res.status_code == 200
    assert "xml" in event_res.headers.get("content-type", "").lower()
    assert "<Response>" in event_res.text

