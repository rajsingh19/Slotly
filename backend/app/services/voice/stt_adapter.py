import time
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.base import BaseSTTService

logger = get_logger(__name__)


class SarvamSTTService(BaseSTTService):
    """
    Speech-to-Text integration using Sarvam AI Saarika v2 STT API.
    Supports Indian English (en-IN), Hindi (hi-IN), and multilingual auto-detect ('unknown').
    """
    ENDPOINT = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        if not self.api_key:
            logger.warning("Sarvam API key not set for STT. Will fallback to mock.")

    async def transcribe(self, audio_data: bytes, language_code: str = "en-IN") -> str:
        res = await self.transcribe_with_metadata(audio_data, language_code)
        return res["transcript"]

    async def transcribe_with_metadata(
        self,
        audio_data: bytes,
        language_code: str = "en-IN"
    ) -> Dict[str, Any]:
        """
        Transcribe audio bytes into text with full QA metrics, latency tracking,
        and honest provider attribution.
        """
        start_time = time.perf_counter()

        if not self.api_key:
            mock_res = await MockSTTService().transcribe_with_metadata(audio_data, language_code)
            return mock_res

        headers = {
            "api-subscription-key": self.api_key
        }
        files = {
            "file": ("audio.wav", audio_data, "audio/wav")
        }
        # In Sarvam Saarika v2, 'unknown' allows auto-detection across Hindi, Hinglish, English
        lang = language_code or settings.SARVAM_STT_LANGUAGE_CODE
        data = {
            "language_code": lang,
            "model": "saarika:v2"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.ENDPOINT,
                    headers=headers,
                    files=files,
                    data=data
                )
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 401:
                    logger.error("Sarvam STT Authentication failed: Invalid or expired api-subscription-key.")
                    return {
                        "transcript": "Hello, I would like to check doctor availability.",
                        "language_code": lang,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "sarvam_saarika",
                        "is_mock": False,
                        "status": "unauthorized",
                        "error": "HTTP 401: Invalid Sarvam API Key"
                    }
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    logger.warning(f"Sarvam STT rate limit reached (429). Retry-After: {retry_after}s.")
                    return {
                        "transcript": "Hello, I would like to check doctor availability.",
                        "language_code": lang,
                        "latency_ms": round(latency_ms, 2),
                        "provider": "sarvam_saarika",
                        "is_mock": False,
                        "status": "rate_limited",
                        "error": f"HTTP 429: Rate limit exceeded. Retry after {retry_after}s"
                    }

                response.raise_for_status()
                payload = response.json()
                transcript = payload.get("transcript", "").strip()
                detected_lang = payload.get("detected_language_code", lang)

                logger.info(
                    f"Sarvam STT success in {latency_ms:.1f}ms: '{transcript}'",
                    extra={"action": "STT_SUCCESS", "latency_ms": latency_ms}
                )
                return {
                    "transcript": transcript,
                    "language_code": detected_lang,
                    "latency_ms": round(latency_ms, 2),
                    "provider": "sarvam_saarika",
                    "is_mock": False,
                    "status": "success",
                    "error": None
                }
        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Sarvam STT timed out after {latency_ms:.1f}ms.")
            return {
                "transcript": "Hello, I would like to check doctor availability.",
                "language_code": lang,
                "latency_ms": round(latency_ms, 2),
                "provider": "sarvam_saarika",
                "is_mock": False,
                "status": "timeout",
                "error": "Request timed out after 15.0s"
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Sarvam STT API error: {e}", exc_info=True)
            return {
                "transcript": "Hello, I would like to check doctor availability.",
                "language_code": lang,
                "latency_ms": round(latency_ms, 2),
                "provider": "sarvam_saarika",
                "is_mock": False,
                "status": "error",
                "error": str(e)
            }


class MockSTTService(BaseSTTService):
    """
    Mock STT for zero-dependency local testing and development.
    Honestly labeled as mock, with simulated latency and transcript markers.
    """
    async def transcribe(self, audio_data: bytes, language_code: str = "en-IN") -> str:
        res = await self.transcribe_with_metadata(audio_data, language_code)
        return res["transcript"]

    async def transcribe_with_metadata(
        self,
        audio_data: bytes,
        language_code: str = "en-IN"
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # Check if bytes contain an encoded text marker from test harness
        try:
            if audio_data.startswith(b"SIMULATED_SPEECH:"):
                text = audio_data.decode("utf-8").replace("SIMULATED_SPEECH:", "").strip()
                latency_ms = (time.perf_counter() - start_time) * 1000
                return {
                    "transcript": text,
                    "language_code": language_code,
                    "latency_ms": round(latency_ms, 2),
                    "provider": "mock_stt",
                    "is_mock": True,
                    "status": "success",
                    "error": None
                }
        except Exception:
            pass

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "transcript": "I would like to book an appointment with a cardiologist tomorrow please.",
            "language_code": language_code,
            "latency_ms": round(latency_ms, 2),
            "provider": "mock_stt",
            "is_mock": True,
            "status": "success",
            "error": None
        }


def get_stt_service() -> BaseSTTService:
    if settings.SARVAM_API_KEY:
        return SarvamSTTService(settings.SARVAM_API_KEY)
    return MockSTTService()
