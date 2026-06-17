from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import Settings, get_settings


class Base(DeclarativeBase):
    pass


def build_async_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        echo=False,
    )


def build_sync_engine(settings: Settings):
    return create_engine(
        settings.database_url_sync,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        echo=False,
    )


_settings = get_settings()
async_engine = build_async_engine(_settings)
async_session_factory = async_sessionmaker(
    bind=async_engine, autoflush=False, expire_on_commit=False
)

sync_engine = build_sync_engine(_settings)
sync_session_factory = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_sync_session() -> Generator[Session]:
    with sync_session_factory() as session:
        yield session
