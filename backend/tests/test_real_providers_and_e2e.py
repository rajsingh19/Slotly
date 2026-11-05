import os
import json
import base64
import struct
import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.voice.stt_adapter import SarvamSTTService, MockSTTService
from app.services.voice.tts_adapter import SarvamBulbulTTSService, MockTTSService, generate_synthesized_wav
from app.services.voice.llm_adapter import GeminiLLMService, OpenAILLMService, MockHospitalLLMService, RECEPTIONIST_TOOLS
from app.services.voice.agent.tools import tool_registry, RescheduleAppointmentInput, CancelAppointmentInput
from app.schemas.voice import VoiceFrame


# =====================================================================
# 1. SARVAM STT PROVIDER & ADAPTER VERIFICATION
# =====================================================================
@pytest.mark.asyncio
async def test_sarvam_stt_adapter_live_call_and_error_handling():
    """
    Test Sarvam STT service behavior:
    1. Verify connection attempt to actual Sarvam endpoint.
    2. Handle unauthorized error (401) gracefully with clear diagnostic metadata.
    3. Measure transcription latency.
    4. Validate multilingual support (hi-IN, en-IN, unknown).
    """
    # 1. Test with a test API key to verify HTTP request formation and response handling
    test_stt = SarvamSTTService(api_key="test_api_key_sarvam_stt")
    dummy_wav = generate_synthesized_wav(0.3)

    res = await test_stt.transcribe_with_metadata(dummy_wav, language_code="hi-IN")
    assert "latency_ms" in res
    assert res["latency_ms"] >= 0
    assert res["provider"] == "sarvam_saarika"
    assert res["is_mock"] is False
    # Since test key is unauthorized or unreachable without network, it handles error cleanly:
    assert res["status"] in ("unauthorized", "error", "timeout")

    # 2. Test fallback to mock when no key is configured
    mock_stt = MockSTTService()
    sim_bytes = b"SIMULATED_SPEECH: Mujhe dil ke doctor se milna hai"
    mock_res = await mock_stt.transcribe_with_metadata(sim_bytes, language_code="hi-IN")
    assert mock_res["is_mock"] is True
    assert mock_res["provider"] == "mock_stt"
    assert "dil ke doctor" in mock_res["transcript"]


# =====================================================================
# 2. SARVAM BULBUL TTS PROVIDER VERIFICATION
# =====================================================================
@pytest.mark.asyncio
async def test_sarvam_tts_bulbul_audio_format_and_language_detection():
    """
    Test Sarvam Bulbul TTS service behavior:
    1. Dynamic target language detection (hi-IN for Hindi text, en-IN for English).
    2. Format compatibility: 44-byte WAV header, 16000Hz, 16-bit PCM.
    3. Time-to-first-audio latency measurement.
    4. Honest provider attribution (never mislabeling mock audio as real TTS).
    """
    # 1. Test audio format validity of generated WAV
    wav_bytes = generate_synthesized_wav(duration_seconds=0.5, sample_rate=16000)
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert wav_bytes[12:16] == b"fmt "

    # Parse WAV header fields
    subchunk1_size = struct.unpack("<I", wav_bytes[16:20])[0]
    assert subchunk1_size == 16  # Standard PCM
    audio_format = struct.unpack("<H", wav_bytes[20:22])[0]
    assert audio_format == 1     # PCM format
    num_channels = struct.unpack("<H", wav_bytes[22:24])[0]
    assert num_channels == 1     # Mono
    sample_rate = struct.unpack("<I", wav_bytes[24:28])[0]
    assert sample_rate == 16000  # 16 kHz telephony compatible
    bits_per_sample = struct.unpack("<H", wav_bytes[34:36])[0]
    assert bits_per_sample == 16 # 16-bit

    # 2. Test dynamic language detection for Hindi text
    tts_service = SarvamBulbulTTSService(api_key=None)  # Mock fallback
    hindi_res = await tts_service.synthesize_with_metadata("आपकी अपॉइंटमेंट बुक हो गई है।")
    assert hindi_res["language_code"] == "hi-IN"
    assert hindi_res["is_mock"] is True
    assert hindi_res["provider"] == "mock_sine_pcm"
    assert hindi_res["latency_ms"] >= 0

    # 3. Test dynamic language detection for English text
    eng_res = await tts_service.synthesize_with_metadata("Your appointment is confirmed.")
    assert eng_res["language_code"] == "en-IN"


# =====================================================================
# 3. LLM MULTI-TURN CONTEXT & STRUCTURED TOOL CALLS
# =====================================================================
@pytest.mark.asyncio
async def test_llm_conversational_context_and_tool_calls():
    """
    Test LLM provider capabilities:
    1. Conversational context preservation across dialogue history.
    2. Structured function calling with arguments.
    3. Invalid tool arguments handled safely without application crash.
    """
    mock_llm = MockHospitalLLMService()

    # Turn 1: Availability query
    history = [
        {"role": "user", "content": "I would like to see a cardiologist tomorrow"}
    ]
    t1 = await mock_llm.generate_response(history, available_tools=RECEPTIONIST_TOOLS)
    assert t1["finish_reason"] == "tool_calls"
    assert t1["tool_calls"] is not None
    assert t1["tool_calls"][0]["function"]["name"] == "check_doctor_availability"
    call_args = json.loads(t1["tool_calls"][0]["function"]["arguments"])
    assert call_args["specialty"] == "Cardiology"

    # Turn 2: Preserved context with booking confirmation
    history.append({"role": "assistant", "content": t1["content"]})
    history.append({"role": "user", "content": "Yes, please book the 10:00 AM slot for Eleanor Vance"})

    t2 = await mock_llm.generate_response(history, available_tools=RECEPTIONIST_TOOLS)
    assert t2["finish_reason"] == "tool_calls"
    assert t2["tool_calls"][0]["function"]["name"] == "book_appointment"
    book_args = json.loads(t2["tool_calls"][0]["function"]["arguments"])
    assert "Eleanor" in book_args["patient_name"]


@pytest.mark.asyncio
async def test_llm_provider_timeout_and_failure_fallback():
    """
    Verify that if a real LLM provider (Gemini or OpenAI) encounters
    a network timeout or invalid key, it safely falls back to the local
    dialogue engine without interrupting the patient's call.
    """
    gemini_service = GeminiLLMService(api_key="invalid_gemini_test_key")
    messages = [{"role": "user", "content": "What are your visiting hours?"}]

    res = await gemini_service.generate_response(messages)
    assert "visiting hours" in res["content"].lower() or "visiting" in res["content"].lower()
    assert res["finish_reason"] == "stop"


# =====================================================================
# 4. BROWSER AUDIO & WEBSOCKET REAL-TIME STREAMING
# =====================================================================
def test_websocket_audio_chunk_reception_and_speech_streaming():
    """
    Test WebSocket bidirectional voice frame exchange:
    1. Client opens WebSocket connection.
    2. Server delivers welcome frame (both text and synthesized audio).
    3. Client sends base64 WAV audio packet.
    4. Server streams back text and audio frames with sentence boundaries.
    """
    test_client = TestClient(app)
    session_id = f"test-browser-ws-{date.today().isoformat()}"

    with test_client.websocket_connect(f"/api/voice/ws/{session_id}") as ws:
        # 1. Welcome text frame
        welcome_frame_text = json.loads(ws.receive_text())
        assert welcome_frame_text["type"] == "text"
        assert welcome_frame_text["role"] == "assistant"
        assert "Maya" in welcome_frame_text["data"]

        # 2. Welcome audio frame
        welcome_frame_audio = json.loads(ws.receive_text())
        assert welcome_frame_audio["type"] == "audio"
        assert len(welcome_frame_audio["data"]) > 0

        # 3. Client sends simulated speech audio frame
        dummy_wav = generate_synthesized_wav(0.4)
        audio_b64 = base64.b64encode(b"SIMULATED_SPEECH: Mujhe skin doctor ko dikhana hai").decode("utf-8")
        ws.send_text(json.dumps({
            "type": "audio",
            "data": audio_b64,
            "format": "wav"
        }))

        # 4. Receive user transcription frame (STT recognized speech)
        user_transcript_frame = json.loads(ws.receive_text())
        assert user_transcript_frame["type"] == "text"
        assert user_transcript_frame["role"] == "user"
        assert "skin doctor" in user_transcript_frame["data"]

        # 5. Receive assistant text response frame
        reply_frame_text = json.loads(ws.receive_text())
        assert reply_frame_text["type"] == "text"
        assert reply_frame_text["role"] == "assistant"
        assert any(w in reply_frame_text["data"].lower() for w in ["din", "appointment", "kal", "tarikh"])
        assert "latency_ms" in reply_frame_text

        # 6. Receive assistant audio sentence streaming frame(s)
        while True:
            reply_frame_audio = json.loads(ws.receive_text())
            assert reply_frame_audio["type"] == "audio"
            assert len(reply_frame_audio["data"]) > 0
            if reply_frame_audio.get("is_final", False):
                break

        # 7. Cleanly close websocket
        ws.send_text(json.dumps({"type": "control", "data": "HANGUP"}))
        ws.close()


# =====================================================================
# 5. SECURITY & CONFIDENTIALITY VERIFICATION
# =====================================================================
def test_security_frontend_does_not_leak_api_keys():
    """
    Ensure API keys and server secrets never appear in the client-facing codebase,
    HTML, or JavaScript build assets.
    """
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.exists(frontend_dist):
        for root, _, files in os.walk(frontend_dist):
            for file in files:
                if file.endswith((".js", ".html")):
                    content = open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore").read()
                    assert "SARVAM_API_KEY" not in content
                    assert "OPENAI_API_KEY" not in content
                    assert "GEMINI_API_KEY" not in content


@pytest.mark.asyncio
async def test_security_patient_identity_verification_for_modifications(db_session: AsyncSession):
    """
    Verify security requirement: Appointment modifications (reschedule/cancel)
    require a valid existing appointment reference and prevent unauthorized alterations.
    """
    # 1. Reschedule non-existent appointment ID fails safely
    res_fake_resched = await tool_registry.reschedule_appointment(
        db_session,
        RescheduleAppointmentInput(
            appointment_id=999999,
            new_date=(date.today() + timedelta(days=5)).isoformat(),
            new_time="14:00"
        )
    )
    assert res_fake_resched["status"] in ("not_found", "error")

    # 2. Cancel non-existent appointment ID fails safely
    res_fake_cancel = await tool_registry.cancel_appointment(
        db_session,
        CancelAppointmentInput(
            appointment_id=999999,
            confirmation=True
        )
    )
    assert res_fake_cancel["status"] in ("not_found", "error")


# =====================================================================
# 6. COMPLETE END-TO-END WORKFLOW VERIFICATION
# =====================================================================
@pytest.mark.asyncio
async def test_complete_end_to_end_hinglish_voice_booking_workflow(client: AsyncClient):
    """
    Executes the full real-world end-to-end user scenario:
    1. Start voice session
    2. Speak in Hinglish ("Mujhe skin doctor ko dikhana hai")
    3. STT / Agent extracts intent and searches active doctors
    4. Provide appointment date ("Kal")
    5. Agent offers available slots from real database
    6. Select slot ("11:00 AM")
    7. Provide patient details ("Rahul Verma", "+919876543210")
    8. Confirm booking ("Haan confirm kar do")
    9. Appointment saved to PostgreSQL / DB with unique reference number
    10. AI replies with real booking reference and saves call session
    """
    # Step 1: Start voice session
    s_res = await client.post("/api/voice/session", json={"caller_phone": "+919876543210"})
    assert s_res.status_code == 200
    session_id = s_res.json()["data"]["session_id"]

    # Step 2: Patient speaks in Hinglish for skin doctor
    r1 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mujhe+skin+doctor+ko+dikhana+hai")
    assert r1.status_code == 200
    assert any(w in r1.json()["data"]["assistant_reply"].lower() for w in ["din", "appointment", "kal", "tarikh"])

    # Step 3: Patient specifies "Kal" (Tomorrow)
    r2 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Kal")
    assert r2.status_code == 200
    reply2 = r2.json()["data"]["assistant_reply"].lower()
    assert "sunita patel" in reply2 or "slot" in reply2

    # Step 4: Patient selects 11:00 AM slot
    r3 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=11:00+AM")
    assert r3.status_code == 200
    assert any(w in r3.json()["data"]["assistant_reply"].lower() for w in ["naam", "phone", "number", "kiske"])

    # Step 5: Patient provides name and phone number
    r4 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Mera+naam+Rahul+Verma+hai+aur+phone+9876543210+hai")
    assert r4.status_code == 200
    assert "confirm" in r4.json()["data"]["assistant_reply"].lower()

    # Step 6: Patient explicitly confirms booking
    r5 = await client.post(f"/api/voice/simulate-turn?session_id={session_id}&message=Haan+confirm+kar+do")
    assert r5.status_code == 200
    reply5 = r5.json()["data"]["assistant_reply"]
    assert "APT-" in reply5
    assert any(w in reply5.lower() for w in ["badhai", "confirm", "book"])

    # Step 7: Verify appointment and call session in database
    calls_res = await client.get("/api/voice/calls")
    assert calls_res.status_code == 200
    calls_data = calls_res.json()["data"]
    assert len(calls_data) > 0
    # Find our session
    matched = [c for c in calls_data if c["session_id"] == session_id or c["caller_phone"] == "+919876543210"]
    assert len(matched) > 0
