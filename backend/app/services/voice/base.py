from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseSTTService(ABC):
    """
    Abstract interface for Speech-to-Text providers.
    """
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language_code: str = "en-IN") -> str:
        """
        Transcribe raw audio bytes into text.
        """
        pass


class BaseTTSService(ABC):
    """
    Abstract interface for Text-to-Speech providers.
    """
    @abstractmethod
    async def synthesize(self, text: str, speaker: Optional[str] = None) -> bytes:
        """
        Synthesize text into audio bytes (WAV or MP3 format).
        """
        pass


class BaseLLMService(ABC):
    """
    Abstract interface for LLM dialogue orchestration and tool calling.
    """
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate dialogue turn response and optional tool call invocations.
        Returns:
            {
                "content": str,
                "tool_calls": Optional[List[Dict[str, Any]]],
                "finish_reason": str
            }
        """
        pass
