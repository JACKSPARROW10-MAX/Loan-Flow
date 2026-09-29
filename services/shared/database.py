"""
LoanFlow – Async SQLAlchemy engine and session factory.
Uses the Supabase-hosted PostgreSQL via DATABASE_URL.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

# Convert postgres:// to postgresql+asyncpg:// if needed
_db_url = settings.database_url
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine_kwargs = {"echo": False}
if not _db_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    })

engine = create_async_engine(_db_url, **engine_kwargs)


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency – yields a DB session, auto-closes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables (dev convenience – use Alembic in prod)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
