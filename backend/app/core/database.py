from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

# Configure engine arguments based on driver
engine_kwargs = {
    "echo": settings.DATABASE_ECHO,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

# Create async engine
engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an active database session.
    Automatically handles rollback on exceptions and cleanup.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rollback due to error: {e}", exc_info=True)
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database schema (create tables if not present).
    Used during startup for development and initial migrations.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database tables verified/created successfully using URL: {settings.DATABASE_URL.split('@')[-1]}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        raise
