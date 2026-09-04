from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, update
from starlette.requests import Request

from modules.agent.infra.database.models import AgentModel
from modules.core.infra.database.models import ApiKeyModel, ProjectModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import AuthenticationError, AuthorizationError, NotFoundError
from shared.infra.security import SqlSecurityAuthenticator
from shared.security.access_tokens import AccessTokenCodec
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_SCOPE_TRACES_READ,
    issue_project_api_key,
)
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)
from woobe_api.security.http_guard import HttpSecurityGuard


def _runtime_request(api_key: str) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/agent/runtime/ask",
            "raw_path": b"/agent/runtime/ask",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {api_key}".encode())],
            "client": ("127.0.0.1", 50000),
            "server": ("test", 80),
        }
    )


def _guard(session_factory, settings: Settings) -> HttpSecurityGuard:
    api_key_rate_limiter = ApiKeyRequestLimiter(
        max_requests=100,
        window_seconds=60,
        session_factory=session_factory,
    )
    return HttpSecurityGuard(
        authenticator=SqlSecurityAuthenticator(
            session_factory=session_factory,
            token_codec=AccessTokenCodec(
                signing_key=settings.secret_key,
                issuer=settings.auth_issuer,
                audience=settings.auth_audience,
                ttl_seconds=settings.access_token_ttl_seconds,
                leeway_seconds=settings.auth_clock_skew_seconds,
            ),
            api_key_rate_limiter=api_key_rate_limiter,
        ),
        login_rate_limiter=LoginRateLimiter(
            max_attempts=100,
            window_seconds=60,
            session_factory=session_factory,
        ),
        api_key_concurrency_limiter=ApiKeyConcurrencyLimiter(
            max_concurrency=10,
            session_factory=session_factory,
        ),
        settings=settings,
    )


@pytest.fixture
async def api_key_graph():
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    foreign_project_id = uuid4()
    agent_id = uuid4()
    foreign_agent_id = uuid4()
    creator_id = uuid4()
    issued = issue_project_api_key()
    api_key_id = uuid4()

    async with session_factory() as session:
        session.add_all(
            [
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="API key project",
                    slug=f"api-key-project-{project_id}",
                    status="active",
                    data={},
                ),
                ProjectModel(
                    id=foreign_project_id,
                    workspace_id=uuid4(),
                    name="Foreign project",
                    slug=f"foreign-project-{foreign_project_id}",
                    status="active",
                    data={},
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="Owned agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="gpt-test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateful",
                    status="active",
                    settings={},
                ),
                AgentModel(
                    id=foreign_agent_id,
                    project_id=foreign_project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="Foreign agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="gpt-test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateful",
                    status="active",
                    settings={},
                ),
            ]
        )
        await session.flush()

        session.add(
            ApiKeyModel(
                id=api_key_id,
                project_id=project_id,
                credential_id=api_key_id,
                name="Runtime key",
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
                status="active",
                last_used_at=None,
                expires_at=datetime.now(UTC) + timedelta(days=1),
                revoked_at=None,
                created_by_user_id=creator_id,
                rotated_from_id=None,
            )
        )
        await session.commit()

    try:
        yield {
            "settings": settings,
            "session_factory": session_factory,
            "api_key_id": api_key_id,
            "api_key": issued.value,
            "project_id": project_id,
            "foreign_project_id": foreign_project_id,
            "agent_id": agent_id,
            "foreign_agent_id": foreign_agent_id,
        }
    finally:
        async with session_factory() as session:
            await session.execute(delete(ApiKeyModel).where(ApiKeyModel.id == api_key_id))
            await session.execute(
                delete(AgentModel).where(
                    AgentModel.id.in_([agent_id, foreign_agent_id])
                )
            )
            await session.execute(
                delete(ProjectModel).where(
                    ProjectModel.id.in_([project_id, foreign_project_id])
                )
            )
            await session.commit()
        await engine.dispose()


async def _update_key(graph, **values) -> None:
    async with graph["session_factory"]() as session:
        await session.execute(
            update(ApiKeyModel)
            .where(ApiKeyModel.id == graph["api_key_id"])
            .values(**values)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_runtime_api_key_accepts_its_project_and_owned_agent(api_key_graph) -> None:
    graph = api_key_graph
    principal = await _guard(
        graph["session_factory"], graph["settings"]
    ).authenticate_and_authorize(
        _runtime_request(graph["api_key"]),
        body={
            "project_id": str(graph["project_id"]),
            "agent_id": str(graph["agent_id"]),
            "message": "hello",
        },
        query_params={},
        path_params={},
    )

    assert principal is not None
    assert principal.project_id == graph["project_id"]
    assert API_KEY_SCOPE_RUNTIME_EXECUTE in principal.scopes


@pytest.mark.asyncio
async def test_runtime_api_key_hides_foreign_project_and_agent(api_key_graph) -> None:
    graph = api_key_graph

    with pytest.raises(NotFoundError, match="Resource not found"):
        await _guard(
            graph["session_factory"], graph["settings"]
        ).authenticate_and_authorize(
            _runtime_request(graph["api_key"]),
            body={
                "project_id": str(graph["foreign_project_id"]),
                "agent_id": str(graph["foreign_agent_id"]),
                "message": "cross-project attempt",
            },
            query_params={},
            path_params={},
        )


@pytest.mark.asyncio
async def test_runtime_api_key_rejects_missing_execute_scope(api_key_graph) -> None:
    graph = api_key_graph
    await _update_key(graph, scopes=[API_KEY_SCOPE_TRACES_READ])

    with pytest.raises(AuthorizationError, match="scope is not sufficient"):
        await _guard(
            graph["session_factory"], graph["settings"]
        ).authenticate_and_authorize(
            _runtime_request(graph["api_key"]),
            body={
                "project_id": str(graph["project_id"]),
                "agent_id": str(graph["agent_id"]),
                "message": "hello",
            },
            query_params={},
            path_params={},
        )


@pytest.mark.asyncio
async def test_runtime_api_key_rejects_revoked_key(api_key_graph) -> None:
    graph = api_key_graph
    await _update_key(
        graph,
        status="revoked",
        revoked_at=datetime.now(UTC),
    )

    with pytest.raises(AuthenticationError, match="API key is inactive"):
        await _guard(
            graph["session_factory"], graph["settings"]
        ).authenticate_and_authorize(
            _runtime_request(graph["api_key"]),
            body={"project_id": str(graph["project_id"]), "message": "hello"},
            query_params={},
            path_params={},
        )


@pytest.mark.asyncio
async def test_runtime_api_key_rejects_expired_key(api_key_graph) -> None:
    graph = api_key_graph
    await _update_key(graph, expires_at=datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(AuthenticationError, match="API key is inactive"):
        await _guard(
            graph["session_factory"], graph["settings"]
        ).authenticate_and_authorize(
            _runtime_request(graph["api_key"]),
            body={"project_id": str(graph["project_id"]), "message": "hello"},
            query_params={},
            path_params={},
        )
