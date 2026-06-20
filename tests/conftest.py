import os
from pathlib import Path
import shutil
import subprocess
import sys
from collections.abc import AsyncIterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from shared.infra.config import Settings


def pytest_sessionstart(session: pytest.Session) -> None:
    if os.environ.get("CI", "").lower() != "true":
        return

    executable = shutil.which("pyright")
    if executable is None:
        raise pytest.UsageError("pyright executable is required by CI")

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [executable, "src", "migrations"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        )
        raise pytest.UsageError(
            "Full-repository Pyright gate failed:\n" + output
        )


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
