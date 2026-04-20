from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config import get_settings

settings = get_settings()

# ── Engine ─────────────────────────────────────────────────────────────────────
# NullPool is used for Lambda/serverless compatibility if ever needed.
# For EC2 + RDS Proxy, remove NullPool and let SQLAlchemy manage its pool.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # RDS Proxy handles connection pooling externally — keep pool_size modest.
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Detect stale connections before handing them out.
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Celery worker engine ────────────────────────────────────────────────────────
# Celery tasks run async code via asyncio.run(), which creates a new event loop
# per task. A pooled engine holds asyncpg connections tied to a previous loop,
# causing "Future attached to a different loop" errors. NullPool opens a fresh
# connection for each task and closes it immediately — no cross-loop reuse.
celery_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,
)

CelerySessionFactory = async_sessionmaker(
    bind=celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency. Yields an AsyncSession and ensures it is closed after
    the request regardless of success or error.

    Usage in a router:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
