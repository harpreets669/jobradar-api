from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

_is_remote = not settings.database_url.startswith("postgresql+asyncpg://localhost") and \
             not settings.database_url.startswith("postgresql+asyncpg://I2343")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # test connection before use — fixes "connection is closed"
    pool_recycle=1800,        # recycle connections every 30 min
    connect_args={"ssl": "require"} if _is_remote else {},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    import app.models.job  # noqa: F401 — registers models with Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
