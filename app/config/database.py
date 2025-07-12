from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}",
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


async def get_db():  # type: ignore
    """
    Get a database session.
    This function is used to create a new database session.
    It is used in the dependency injection system of FastAPI.
    """
    async with AsyncSessionLocal() as session:  # type: ignore
        yield session


def get_db_conn():
    """
    Get a DB connection.
    This function is used to create a new DB connection.
    """
    return engine.connect()
