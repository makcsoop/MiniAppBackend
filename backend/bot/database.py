from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from bot.config import settings

def get_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

engine = create_async_engine(
    get_async_url(settings.DATABASE_URL),
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)