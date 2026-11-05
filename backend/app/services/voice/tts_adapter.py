import re
import time
import base64
import struct
import math
import httpx
from typing import Optional, Dict, Any, List, Tuple
from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.base import BaseTTSService

logger = get_logger(__name__)


def generate_synthesized_wav(duration_seconds: float = 0.5, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """
    Generate a clean standard 16-bit PCM WAV byte sequence for local mock audio.
    Used for offline testing so the browser audio context or HTML5 Audio element
    can play it natively with verified 44-byte header structure.
    """
    num_samples = int(sample_rate * duration_seconds)
    audio_data = bytearray()
    
    for i in range(num_samples):
        # Soft tone with envelope fading to avoid click on boundaries
        envelope = math.sin(math.pi * i / num_samples)
        sample = int(16000 * 0.2 * envelope * math.sin(2 * math.pi * freq * (i / sample_rate)))
        audio_data.extend(struct.pack("<h", max(-32768, min(32767, sample))))

    # Build standard 44-byte WAV header
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
    Supports expressive human-like speech in Hindi (hi-IN) and Indian English (en-IN).
    """
    ENDPOINT = "https://api.sarvam.ai/text-to-speech"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        if not self.api_key:
            logger.warning("Sarvam API key not set for TTS. Falling back to mock synthesis.")

    async def synthesize(self, text: str, speaker: Optional[str] = None) -> bytes:
        res = await self.synthesize_with_metadata(text, speaker)
        return res["audio_bytes"]

    async def synthesize_with_metadata(
        self,
        text: str,
        speaker: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize text into audio with latency measurement and honest provider attribution.
        Never mislabels mock audio as Sarvam Bulbul output.
        """
        start_time = time.perf_counter()

        if not self.api_key:
            return await MockTTSService().synthesize_with_metadata(text, speaker, language_code)

        # Detect language if not explicitly provided
        if not language_code:
            is_hindi = bool(re.search(r"[\u0900-\u097F]", text))
            target_lang = "hi-IN" if is_hindi else "en-IN"
        else:
            target_lang = language_code

        clean_text = text.strip()[:500]  # Respect Bulbul chunk limit
        spk = speaker or settings.SARVAM_TTS_SPEAKER

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [clean_text],
            "target_language_code": target_lang,
            "speaker": spk,
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
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 401:
                    logger.error("Sarvam TTS Authentication failed: Invalid or expired api-subscription-key.")
                    mock_bytes = generate_synthesized_wav(0.4)
                    return {
                        "audio_bytes": mock_bytes,
                        "format": "wav",
                        "sample_rate": 16000,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "mock_sine_pcm",
                        "is_mock": True,
                        "speaker": spk,
                        "language_code": target_lang,
                        "status": "unauthorized",
                        "error": "HTTP 401: Invalid Sarvam API Key"
                    }
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    logger.warning(f"Sarvam TTS rate limit reached (429). Retry-After: {retry_after}s.")
                    mock_bytes = generate_synthesized_wav(0.4)
                    return {
                        "audio_bytes": mock_bytes,
                        "format": "wav",
                        "sample_rate": 16000,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "mock_sine_pcm",
                        "is_mock": True,
                        "speaker": spk,
                        "language_code": target_lang,
                        "status": "rate_limited",
                        "error": f"HTTP 429: Rate limit exceeded. Retry after {retry_after}s"
                    }

                response.raise_for_status()
                data = response.json()
                audios = data.get("audios", [])
                if audios:
                    audio_b64 = audios[0]
                    audio_bytes = base64.b64decode(audio_b64)
                    logger.info(
                        f"Sarvam Bulbul TTS synthesized {len(audio_bytes)} bytes in {latency_ms:.1f}ms",
                        extra={"action": "TTS_SUCCESS", "latency_ms": latency_ms}
                    )
                    return {
                        "audio_bytes": audio_bytes,
                        "format": "wav",
                        "sample_rate": 16000,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "sarvam_bulbul",
                        "is_mock": False,
                        "speaker": spk,
                        "language_code": target_lang,
                        "status": "success",
                        "error": None
                    }
                else:
                    logger.warning("Empty audio array from Sarvam TTS. Returning mock WAV.")
                    mock_bytes = generate_synthesized_wav(0.4)
                    return {
                        "audio_bytes": mock_bytes,
                        "format": "wav",
                        "sample_rate": 16000,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "mock_sine_pcm",
                        "is_mock": True,
                        "speaker": spk,
                        "language_code": target_lang,
                        "status": "empty_response",
                        "error": "Sarvam API returned empty audio array"
                    }
        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Sarvam TTS timed out after {latency_ms:.1f}ms.")
            mock_bytes = generate_synthesized_wav(0.4)
            return {
                "audio_bytes": mock_bytes,
                "format": "wav",
                "sample_rate": 16000,
                "latency_ms": round(latency_ms, 2),
                "provider": "mock_sine_pcm",
                "is_mock": True,
                "speaker": spk,
                "language_code": target_lang,
                "status": "timeout",
                "error": "Request timed out after 15.0s"
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Sarvam TTS error: {e}. Falling back to mock audio generator.", exc_info=True)
            mock_bytes = generate_synthesized_wav(0.4)
            return {
                "audio_bytes": mock_bytes,
                "format": "wav",
                "sample_rate": 16000,
                "latency_ms": round(latency_ms, 2),
                "provider": "mock_sine_pcm",
                "is_mock": True,
                "speaker": spk,
                "language_code": target_lang,
                "status": "error",
                "error": str(e)
            }


class MockTTSService(BaseTTSService):
    """
    Mock TTS engine for zero-dependency local testing.
    Generates standard playable WAV chunks matching text length, honestly marked as mock.
    """
    async def synthesize(self, text: str, speaker: Optional[str] = None) -> bytes:
        res = await self.synthesize_with_metadata(text, speaker)
        return res["audio_bytes"]

    async def synthesize_with_metadata(
        self,
        text: str,
        speaker: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        words = len(text.split())
        duration = max(0.3, min(2.5, words * 0.12))
        audio = generate_synthesized_wav(duration_seconds=duration, freq=520.0)
        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "audio_bytes": audio,
            "format": "wav",
            "sample_rate": 16000,
            "latency_ms": round(latency_ms, 2),
            "provider": "mock_sine_pcm",
            "is_mock": True,
            "speaker": speaker or "mock_maya",
            "language_code": language_code or ("hi-IN" if re.search(r"[\u0900-\u097F]", text) else "en-IN"),
            "status": "success",
            "error": None
        }


def get_tts_service() -> BaseTTSService:
    if settings.SARVAM_API_KEY:
        return SarvamBulbulTTSService(settings.SARVAM_API_KEY)
    return MockTTSService()
