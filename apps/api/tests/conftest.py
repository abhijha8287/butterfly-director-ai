from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config.settings import get_settings
from app.core.deps import get_db
from app.integrations.redis_client import get_redis_pool
from app.main import app


@pytest.fixture(autouse=True)
def _fresh_redis_pool_per_test() -> Generator[None]:
    """RateLimitMiddleware holds one Redis connection pool for the app's lifetime,
    but pytest-asyncio gives each test function its own event loop. A pool's TCP
    connections are bound to whichever loop was running when they opened, so a
    pool first used in test A breaks in test B's loop - and by then that loop is
    already closed, so even a graceful pool.disconnect() raises trying to close
    the dead transport. reset() just drops the stale connection references
    (no I/O, so no need to be async), so the pool opens fresh connections bound
    to the current loop.
    """
    pool = get_redis_pool()
    pool.reset()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Real Postgres-backed session wrapped in a SAVEPOINT that is always rolled
    back, so tests can call session.commit() (as the real services do) without
    ever persisting data. Standard SQLAlchemy "join a session into an external
    transaction" recipe, adapted for asyncio.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url)

    async with engine.connect() as conn:
        await conn.begin()
        await conn.begin_nested()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sess: object, transaction: object) -> None:
            if conn.closed:
                return
            if not conn.sync_connection.in_nested_transaction():
                conn.sync_connection.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
