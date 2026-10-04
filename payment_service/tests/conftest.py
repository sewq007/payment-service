from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.database import Base, get_session
from app.main import app
from app.services import TARIFFS_SEED


@pytest_asyncio.fixture
async def client(tmp_path) -> AsyncGenerator[AsyncClient, None]:
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    TestSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as s:
        for t in TARIFFS_SEED:
            s.add(models.Tariff(**t))
        await s.commit()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()