from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.redis import cache_client, CacheClient
from app.services.voice.pipeline import voice_orchestrator, VoicePipelineOrchestrator

# Alias for backwards compatibility with voice and telephony modules
get_database_session = get_db


def get_cache() -> CacheClient:
    return cache_client


def get_voice_pipeline() -> VoicePipelineOrchestrator:
    return voice_orchestrator
