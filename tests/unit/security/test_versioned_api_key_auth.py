from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from shared.infra.errors import AuthenticationError
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_VERSION,
    issue_runtime_api_key,
)
from shared.security.http_guard import HttpSecurityGuard


class FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeSession:
    def __init__(self, row: object) -> None:
        self.row = row
        self.calls: list[tuple[str, dict]] = []
        self.commit = AsyncMock()

    async def execute(self, statement, params: dict):
        sql = str(statement)
        self.calls.append((sql, params))
        if "FROM core.api_keys" in sql:
            return FakeResult([self.row])
        return SimpleNamespace()


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


def runtime_row(*, issued, environment: str):
    agent_id = uuid4()
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        key_prefix=issued.public_prefix,
        key_hash=issued.digest,
        key_version=issued.key_version,
        scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
        kind="runtime",
        agent_id=agent_id,
        target_type="agent",
        target_id=agent_id,
        environment=environment,
        interfaces=["http"],
        status="active",
        revoked_at=None,
        expires_at=None,
    )


def build_guard(session: FakeSession) -> HttpSecurityGuard:
    guard = HttpSecurityGuard.__new__(HttpSecurityGuard)
    guard._session_factory = lambda: FakeSessionContext(session)
    guard._api_key_rate_limiter = SimpleNamespace(consume=AsyncMock())
    return guard


@pytest.mark.asyncio
async def test_guard_uses_version_parsed_from_woobe_key() -> None:
    issued = issue_runtime_api_key("production")
    row = runtime_row(issued=issued, environment="production")
    session = FakeSession(row)
    guard = build_guard(session)
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/v1/run"))

    principal = await guard._authenticate_api_key(
        request=request,
        credentials=issued.value,
        body={"message": "Hello"},
        query_params={},
        path_params={},
    )

    select_params = session.calls[0][1]
    assert select_params["key_version"] == API_KEY_VERSION
    assert principal.environment == "production"
    assert principal.key_prefix.startswith("woobe_production_")


@pytest.mark.asyncio
async def test_guard_rejects_environment_prefix_binding_mismatch() -> None:
    issued = issue_runtime_api_key("production")
    row = runtime_row(issued=issued, environment="staging")
    session = FakeSession(row)
    guard = build_guard(session)
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/v1/run"))

    with pytest.raises(AuthenticationError, match="Invalid API key"):
        await guard._authenticate_api_key(
            request=request,
            credentials=issued.value,
            body={"message": "Hello"},
            query_params={},
            path_params={},
        )
