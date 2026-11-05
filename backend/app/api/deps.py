from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.redis import cache_client, CacheClient
from app.services.hospital_service import hospital_service, HospitalService
from app.services.voice.pipeline import voice_orchestrator, VoicePipelineOrchestrator


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_cache() -> CacheClient:
    return cache_client


def get_hospital_svc() -> HospitalService:
    return hospital_service


def get_voice_pipeline() -> VoicePipelineOrchestrator:
    return voice_orchestrator
