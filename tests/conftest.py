import os
import sys
from collections.abc import AsyncIterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from shared.infra.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    from main import create_app

    return create_app()


@pytest.fixture
async def async_client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def settings() -> Settings:
    return Settings()
