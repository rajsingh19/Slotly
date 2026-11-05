import uuid
import json
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.schemas.voice import VoiceFrame


def test_voice_websocket_streaming_exchange():
    """
    Test real-time bidirectional WebSocket voice streaming endpoint:
    1. Connects to /api/voice/ws/{session_id}
    2. Receives welcome text frame and audio greeting frame
    3. Sends text request inquiring about doctor availability
    4. Receives user echo frame, spoken text frame, and sentence audio chunk frames
    5. Sends control HANGUP frame and cleanly disconnects
    """
    client = TestClient(app)
    session_id = f"test-ws-session-{uuid.uuid4().hex[:8]}"

    with client.websocket_connect(f"/api/voice/ws/{session_id}") as websocket:
        # 1. Receive welcome greeting text frame
        welcome_text_pkt = websocket.receive_text()
        frame1 = json.loads(welcome_text_pkt)
        assert frame1["type"] == "text"
        assert frame1["role"] == "assistant"
        assert "welcome" in frame1["data"].lower() or "maya" in frame1["data"].lower()

        # 2. Receive welcome greeting audio frame
        welcome_audio_pkt = websocket.receive_text()
        frame2 = json.loads(welcome_audio_pkt)
        assert frame2["type"] == "audio"
        assert len(frame2["data"]) > 0

        # 3. Send caller inquiry turn
        user_msg = VoiceFrame(type="text", data="Do you have an available cardiologist tomorrow?")
        websocket.send_text(user_msg.model_dump_json())

        # 4. Receive user speech transcription echo
        user_echo_pkt = websocket.receive_text()
        frame_user = json.loads(user_echo_pkt)
        assert frame_user["type"] == "text"
        assert frame_user["role"] == "user"
        assert "cardiologist" in frame_user["data"]

        # 5. Receive assistant text response frame
        asst_text_pkt = websocket.receive_text()
        frame_asst = json.loads(asst_text_pkt)
        assert frame_asst["type"] == "text"
        assert frame_asst["role"] == "assistant"
        assert "available" in frame_asst["data"].lower() or "doctor" in frame_asst["data"].lower()

        # 6. Receive streaming audio frames (sentence-boundary chunks)
        while True:
            audio_chunk_pkt = websocket.receive_text()
            frame_chunk = json.loads(audio_chunk_pkt)
            assert frame_chunk["type"] == "audio"
            assert len(frame_chunk["data"]) > 0
            if frame_chunk.get("is_final", False):
                break

        # 7. Send HANGUP control frame
        hangup = VoiceFrame(type="control", data="HANGUP")
        websocket.send_text(hangup.model_dump_json())
        websocket.close()

