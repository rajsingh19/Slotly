from fastapi import APIRouter
from app.api.v1.doctors import router as doctors_router
from app.api.v1.availability import router as availability_router
from app.api.v1.patients import router as patients_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.calls import router as calls_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.health import router as health_router
from app.api.v1.hospital import router as hospital_router
from app.api.v1.voice import router as voice_router
from app.api.v1.telephony import router as telephony_router

api_router = APIRouter()

api_router.include_router(doctors_router)
api_router.include_router(availability_router)
api_router.include_router(patients_router)
api_router.include_router(appointments_router)
api_router.include_router(calls_router)
api_router.include_router(analytics_router)
api_router.include_router(health_router)
api_router.include_router(hospital_router)
api_router.include_router(voice_router)
api_router.include_router(telephony_router)
