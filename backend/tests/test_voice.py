import pytest
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
