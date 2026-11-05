import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "AI Hospital Receptionist Voice Agent"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    SECRET_KEY: str = "dev-secret-key-for-local-testing-only-12345"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            import json
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    return [i.strip() for i in v.split(",")]
            return v
        raise ValueError(v)

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"  # 'json' or 'console'

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./hospital.db"
    DATABASE_ECHO: bool = False

    # Cache / Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # LLM Provider
    LLM_PROVIDER: str = "mock"  # "mock", "gemini", "openai", "groq"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "gemini-1.5-flash"
    LLM_TEMPERATURE: float = 0.2

    # Sarvam AI STT & TTS
    SARVAM_API_KEY: str = ""
    SARVAM_STT_LANGUAGE_CODE: str = "en-IN"
    SARVAM_TTS_MODEL: str = "bulbul:v1"
    SARVAM_TTS_SPEAKER: str = "ananya"

    # Telephony - Plivo
    PLIVO_ENABLED: bool = False
    PLIVO_AUTH_ID: str = ""
    PLIVO_AUTH_TOKEN: str = ""
    PLIVO_PHONE_NUMBER: str = ""
    PLIVO_APP_URL: str = "http://localhost:8000"

    # Hospital Details
    HOSPITAL_NAME: str = "Apex Multi-Specialty Hospital"
    HOSPITAL_PHONE: str = "+1-800-555-0199"
    HOSPITAL_ADDRESS: str = "742 Evergreen Healthcare Blvd, Medical District"
    HOSPITAL_EMERGENCY_PHONE: str = "108"
    HOSPITAL_VISITING_HOURS: str = "General Wards: 4:00 PM - 7:00 PM Daily | ICU: 11:00 AM - 12:00 PM"
    TIMEZONE: str = "Asia/Kolkata"
    MAX_CALL_DURATION_SECONDS: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
