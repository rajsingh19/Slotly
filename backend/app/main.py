import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, AsyncSessionLocal
from app.seeds.seed_data import seed_initial_data
from app.api.v1.router import api_router
from app.api.v1.health import router as root_health_router

setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = get_logger("hospital.voice.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle management.
    """
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    
    # Initialize database schema
    await init_db()

    # Seed initial hospital, 5 doctors, and appointment slots
    async with AsyncSessionLocal() as session:
        try:
            await seed_initial_data(session)
        except Exception as e:
            logger.error(f"Error seeding database: {e}", exc_info=True)

    yield

    logger.info("Shutting down application resources...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-oriented AI Hospital Receptionist & Appointment Booking API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Middleware injecting trace ID and logging request latency.
    """
    trace_id = request.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:8]}")
    start_time = time.time()
    
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    response.headers["X-Request-ID"] = trace_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    if not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi"):
        logger.info(
            f"{request.method} {request.url.path} returned {response.status_code} in {duration_ms:.1f}ms",
            extra={
                "trace_id": trace_id,
                "status_code": response.status_code,
                "latency_ms": duration_ms,
                "path": request.url.path,
                "method": request.method,
            }
        )
    return response


# Mount API routes under /api and /api/v1 for compatibility
app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")

# Mount root health check at /health
app.include_router(root_health_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_health": "/api/health",
        "doctors": "/api/doctors",
        "availability": "/api/availability",
        "appointments": "/api/appointments",
        "calls": "/api/calls",
        "analytics": "/api/analytics",
    }
