from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from starlette.requests import Request

from modules.core.infra.database.models import ProjectModel
from modules.core.infra.services.control_key_service import ControlKeyService
from modules.identity.infra.database.models import WorkspaceModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.infra.security import SqlSecurityAuthenticator
from shared.security.access_tokens import AccessTokenCodec
from shared.security.api_keys import issue_control_api_key
from shared.security.principal import ControlPlanePrincipal
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)
from woobe_api.security.http_guard import HttpSecurityGuard


def _request(api_key: str, project_id) -> Request:
    path = f"/core/projects/{project_id}"
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {api_key}".encode())],
            "client": ("127.0.0.1", 50000),
            "server": ("test", 80),
        }
    )


def _guard(session_factory, settings: Settings) -> HttpSecurityGuard:
    limiter = ApiKeyRequestLimiter(
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
            api_key_rate_limiter=limiter,
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
async def control_key_graph():
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    workspace_id = uuid4()
    project_id = uuid4()
    ungranted_project_id = uuid4()
    control_key_id = uuid4()
    grant_id = uuid4()
    issued = issue_control_api_key()

    async with session_factory() as session:
        session.add(
            WorkspaceModel(
                id=workspace_id,
                name="CLI workspace",
                slug=f"cli-workspace-{workspace_id}",
                status="active",
            )
        )
        await session.flush()
        session.add_all(
            [
                ProjectModel(
                    id=project_id,
                    workspace_id=workspace_id,
                    name="Granted project",
                    slug=f"granted-{project_id}",
                    status="active",
                    data={},
                ),
                ProjectModel(
                    id=ungranted_project_id,
                    workspace_id=workspace_id,
                    name="Ungrant project",
                    slug=f"ungranted-{ungranted_project_id}",
                    status="active",
                    data={},
                ),
            ]
        )
        await session.flush()
        await session.execute(
            text(
                """
                INSERT INTO core.workspace_control_keys
                    (id, workspace_id, credential_id, name, key_prefix,
                     key_hash, key_version, permissions, status, expires_at,
                     created_at, updated_at)
                VALUES
                    (:id, :workspace_id, :credential_id, 'CI control key',
                     :key_prefix, :key_hash, :key_version,
                     CAST(:permissions AS jsonb), 'active', :expires_at,
                     :now, :now)
                """
            ),
            {
                "id": control_key_id,
                "workspace_id": workspace_id,
                "credential_id": control_key_id,
                "key_prefix": issued.public_prefix,
                "key_hash": issued.digest,
                "key_version": issued.key_version,
                "permissions": json.dumps(["workspace:read", "projects:create"]),
                "expires_at": datetime.now(UTC) + timedelta(days=1),
                "now": datetime.now(UTC),
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO core.workspace_control_key_project_grants
                    (id, control_key_id, project_id, permissions,
                     created_at, updated_at)
                VALUES
                    (:id, :control_key_id, :project_id,
                     CAST(:permissions AS jsonb), :now, :now)
                """
            ),
            {
                "id": grant_id,
                "control_key_id": control_key_id,
                "project_id": project_id,
                "permissions": json.dumps(["project:read"]),
                "now": datetime.now(UTC),
            },
        )
        await session.commit()

    try:
        yield {
            "settings": settings,
            "session_factory": session_factory,
            "api_key": issued.value,
            "control_key_id": control_key_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "ungranted_project_id": ungranted_project_id,
        }
    finally:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM core.workspace_control_key_project_grants
                    WHERE control_key_id = :control_key_id
                    """
                ),
                {"control_key_id": control_key_id},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM core.workspace_control_keys
                    WHERE id = :control_key_id
                    """
                ),
                {"control_key_id": control_key_id},
            )
            await session.execute(
                delete(ProjectModel).where(
                    ProjectModel.id.in_([project_id, ungranted_project_id])
                )
            )
            await session.execute(
                delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_key_authenticates_and_enforces_project_grant(
    control_key_graph,
) -> None:
    graph = control_key_graph
    principal = await _guard(
        graph["session_factory"],
        graph["settings"],
    ).authenticate_and_authorize(
        _request(graph["api_key"], graph["project_id"]),
        body=None,
        query_params={},
        path_params={"project_id": str(graph["project_id"])},
    )

    assert isinstance(principal, ControlPlanePrincipal)
    assert principal.workspace_id == graph["workspace_id"]
    assert principal.api_key_id == graph["control_key_id"]

    with pytest.raises(NotFoundError, match="Resource not found"):
        await _guard(
            graph["session_factory"],
            graph["settings"],
        ).authenticate_and_authorize(
            _request(graph["api_key"], graph["ungranted_project_id"]),
            body=None,
            query_params={},
            path_params={
                "project_id": str(graph["ungranted_project_id"]),
            },
        )


@pytest.mark.asyncio
async def test_control_key_rejects_missing_project_permission(
    control_key_graph,
) -> None:
    graph = control_key_graph
    async with graph["session_factory"]() as session:
        await session.execute(
            text(
                """
                UPDATE core.workspace_control_key_project_grants
                SET permissions = '[]'::jsonb
                WHERE control_key_id = :control_key_id
                  AND project_id = :project_id
                """
            ),
            {
                "control_key_id": graph["control_key_id"],
                "project_id": graph["project_id"],
            },
        )
        await session.commit()

    with pytest.raises(AuthorizationError, match="Project permission"):
        await _guard(
            graph["session_factory"],
            graph["settings"],
        ).authenticate_and_authorize(
            _request(graph["api_key"], graph["project_id"]),
            body=None,
            query_params={},
            path_params={"project_id": str(graph["project_id"])},
        )


@pytest.mark.asyncio
async def test_project_creator_control_key_receives_full_grant(
    control_key_graph,
) -> None:
    graph = control_key_graph
    principal = ControlPlanePrincipal(
        api_key_id=graph["control_key_id"],
        credential_id=graph["control_key_id"],
        workspace_id=graph["workspace_id"],
        key_prefix="woobe_control_test",
        permissions=frozenset({"workspace:read", "projects:create"}),
        authenticated_at=datetime.now(UTC),
    )

    await ControlKeyService(graph["session_factory"]).grant_created_project(
        principal=principal,
        project_id=graph["ungranted_project_id"],
    )

    async with graph["session_factory"]() as session:
        result = await session.execute(
            text(
                """
                SELECT permissions
                FROM core.workspace_control_key_project_grants
                WHERE control_key_id = :control_key_id
                  AND project_id = :project_id
                """
            ),
            {
                "control_key_id": graph["control_key_id"],
                "project_id": graph["ungranted_project_id"],
            },
        )
        permissions = set(result.scalar_one())

    assert "project:update" in permissions
    assert "agent:write" in permissions
    assert "network:production" in permissions
    assert "api_key:write" in permissions
