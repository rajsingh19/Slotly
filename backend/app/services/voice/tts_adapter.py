import base64
import struct
import math
import httpx
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.base import BaseTTSService

logger = get_logger(__name__)


def generate_synthesized_wav(duration_seconds: float = 0.5, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """
    Generate a clean standard PCM WAV byte sequence for local mock audio.
    Used so the browser audio context or HTML5 Audio element can play it natively.
    """
    num_samples = int(sample_rate * duration_seconds)
    audio_data = bytearray()
    
    for i in range(num_samples):
        # Soft tone with envelope fading to avoid click
        envelope = math.sin(math.pi * i / num_samples)
        sample = int(16000 * 0.2 * envelope * math.sin(2 * math.pi * freq * (i / sample_rate)))
        audio_data.extend(struct.pack("<h", max(-32768, min(32767, sample))))

    # Build 44-byte WAV header
    byte_rate = sample_rate * 2  # 16-bit mono
    block_align = 2
    total_data_len = len(audio_data)
    total_file_len = total_data_len + 36

    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", total_file_len))
    header.extend(b"WAVE")
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", 16))          # Subchunk1Size (16 for PCM)
    header.extend(struct.pack("<H", 1))           # AudioFormat (1 = PCM)
    header.extend(struct.pack("<H", 1))           # NumChannels (1 = Mono)
    header.extend(struct.pack("<I", sample_rate)) # SampleRate
    header.extend(struct.pack("<I", byte_rate))   # ByteRate
    header.extend(struct.pack("<H", block_align)) # BlockAlign
    header.extend(struct.pack("<H", 16))          # BitsPerSample
    header.extend(b"data")
    header.extend(struct.pack("<I", total_data_len))

    return bytes(header + audio_data)


class SarvamBulbulTTSService(BaseTTSService):
    """
    Text-to-Speech integration using Sarvam AI Bulbul TTS API.
    Supports expressive human-like speech with various Indian accents and speakers.
    """
    ENDPOINT = "https://api.sarvam.ai/text-to-speech"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        if not self.api_key:
            logger.warning("Sarvam API key not set for TTS. Falling back to mock synthesis.")

    async def synthesize(self, text: str, speaker: Optional[str] = None) -> bytes:
        if not self.api_key:
            return await MockTTSService().synthesize(text, speaker)

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Clean text
        clean_text = text.strip()[:500]  # Respect reasonable chunk limit
        
        payload = {
            "inputs": [clean_text],
            "target_language_code": "en-IN",
            "speaker": speaker or settings.SARVAM_TTS_SPEAKER,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.2,
            "speech_sample_rate": 16000,
            "enable_preprocessing": True,
            "model": settings.SARVAM_TTS_MODEL,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                audios = data.get("audios", [])
                if audios:
                    audio_b64 = audios[0]
                    audio_bytes = base64.b64decode(audio_b64)
                    logger.info(f"Sarvam Bulbul TTS synthesized {len(audio_bytes)} bytes", extra={"action": "TTS_SUCCESS"})
                    return audio_bytes
                else:
                    logger.warning("Empty audio array from Sarvam TTS. Returning mock WAV.")
                    return generate_synthesized_wav(0.4)
        except Exception as e:
            logger.error(f"Sarvam TTS error: {e}. Falling back to mock audio generator.", exc_info=True)
            return generate_synthesized_wav(0.4)


class MockTTSService(BaseTTSService):
    """
    Mock TTS engine for zero-dependency local testing.
    Generates standard playable WAV chunks matching text length.
    """
    async def synthesize(self, text: str, speaker: Optional[str] = None) -> bytes:
        # Approximate duration: ~120 words per minute -> 0.15s per word, bounded between 0.3s and 2.5s
        words = len(text.split())
        duration = max(0.3, min(2.5, words * 0.12))
        return generate_synthesized_wav(duration_seconds=duration, freq=520.0)


def get_tts_service() -> BaseTTSService:
    if settings.SARVAM_API_KEY:
        return SarvamBulbulTTSService(settings.SARVAM_API_KEY)
    return MockTTSService()
