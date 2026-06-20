import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections.abc import AsyncIterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from httpx import ASGITransport, AsyncClient

from shared.infra.config import Settings

_PYRIGHT_ERROR_BASELINE = 182


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
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    summary = re.search(r"(?P<count>\d+) errors?[,\n]", output)
    if result.returncode == 0:
        error_count = 0
    elif summary is None:
        raise pytest.UsageError(
            "Full-repository Pyright did not produce a parseable summary:\n"
            + output
        )
    else:
        error_count = int(summary.group("count"))

    if error_count > _PYRIGHT_ERROR_BASELINE:
        raise pytest.UsageError(
            "Full-repository Pyright regression: "
            f"{error_count} errors exceeds baseline {_PYRIGHT_ERROR_BASELINE}.\n"
            + output
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
