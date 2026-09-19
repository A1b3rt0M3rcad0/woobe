from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database.project_environment_reader import (
    SQLAlchemyProjectEnvironmentReader,
)
from shared.infra.crypto import encrypt_secret
from shared.infra.errors import ValidationError
from shared.project_environment import PreparedProjectEnvironmentValue


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    async def execute(self, statement, params):
        self.calls.append((statement, params))
        return _Result(self._rows)


@pytest.mark.asyncio
async def test_project_environment_reader_requires_keys_in_same_project() -> None:
    project_id = uuid4()
    session = _Session([("API_URL",), ("API_KEY",)])
    reader = SQLAlchemyProjectEnvironmentReader(
        SimpleNamespace(session=session),
        encryption_key="test-key",
    )

    await reader.require_keys(
        project_id=project_id,
        keys={"API_URL", "API_KEY"},
    )

    assert len(session.calls) == 1
    assert session.calls[0][1]["project_id"] == project_id
    assert sorted(session.calls[0][1]["keys"]) == ["API_KEY", "API_URL"]


@pytest.mark.asyncio
async def test_project_environment_reader_rejects_missing_key() -> None:
    reader = SQLAlchemyProjectEnvironmentReader(
        SimpleNamespace(session=_Session([("API_URL",)])),
        encryption_key="test-key",
    )

    with pytest.raises(ValidationError, match="API_KEY"):
        await reader.require_keys(
            project_id=uuid4(),
            keys={"API_URL", "API_KEY"},
        )


@pytest.mark.asyncio
async def test_project_environment_reader_materializes_secret_only_on_resolution() -> None:
    encryption_key = "test-project-environment-reader-key"
    reader = SQLAlchemyProjectEnvironmentReader(
        SimpleNamespace(session=None),
        encryption_key=encryption_key,
    )
    reader.read_values = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "API_URL": PreparedProjectEnvironmentValue(
                kind="value",
                stored_value="https://api.example.com",
            ),
            "API_KEY": PreparedProjectEnvironmentValue(
                kind="secret",
                stored_value=encrypt_secret("runtime-secret", encryption_key),
            ),
        }
    )

    resolved = await reader.resolve_values(
        project_id=uuid4(),
        environment="production",
        keys={"API_URL", "API_KEY"},
    )

    assert resolved == {
        "API_URL": "https://api.example.com",
        "API_KEY": "runtime-secret",
    }



@pytest.mark.asyncio
async def test_project_environment_reader_skips_database_when_no_keys_are_referenced() -> None:
    session = _Session([])
    reader = SQLAlchemyProjectEnvironmentReader(
        SimpleNamespace(session=session),
        encryption_key="test-key",
    )

    await reader.require_keys(
        project_id=uuid4(),
        keys=set(),
    )

    assert session.calls == []
