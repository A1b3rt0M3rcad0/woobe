from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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


@pytest.mark.asyncio
async def test_delegation_ceiling_survives_database_roundtrip_and_human_rotation(
    control_key_graph,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from modules.core.application.dtos.create_api_key_dtos import CreateApiKeyInput
    from modules.core.application.dtos.api_key_lifecycle_dtos import RotateApiKeyInput
    from modules.core.application.use_cases.create_api_key_use_case import (
        CreateApiKeyUseCase,
    )
    from modules.core.application.use_cases.api_key_lifecycle_use_cases import (
        RotateApiKeyUseCase,
    )
    from modules.core.infra.database.models import ApiKeyModel
    from modules.core.infra.database.repositories import (
        SQLAlchemyApiKeyRepository,
        SQLAlchemyProjectRepository,
    )
    from modules.core.infra.services.api_key_delegation import SqlApiKeyDelegationPolicy
    from shared.contracts.errors import AuthorizationError

    graph = control_key_graph
    ceiling = datetime.now(UTC) + timedelta(hours=2)
    ids = []
    try:
        async with graph["session_factory"]() as session:
            await session.execute(
                text(
                    "UPDATE core.workspace_control_keys SET expires_at=:ceiling WHERE id=:id"
                ),
                {"ceiling": ceiling, "id": graph["control_key_id"]},
            )
            await session.execute(
                text(
                    'UPDATE core.workspace_control_key_project_grants SET permissions=\'["api_key:write","observability:read"]\'::jsonb WHERE control_key_id=:id'
                ),
                {"id": graph["control_key_id"]},
            )
            repo = SQLAlchemyApiKeyRepository(session)
            result = await CreateApiKeyUseCase(
                SQLAlchemyProjectRepository(session),
                repo,
                SimpleNamespace(write=AsyncMock()),
                delegation_policy=SqlApiKeyDelegationPolicy(session),
            ).execute(
                CreateApiKeyInput(
                    project_id=graph["project_id"],
                    name="Persistent ceiling",
                    scopes=["traces:read"],
                    expires_at=ceiling - timedelta(minutes=10),
                    created_by_control_key_id=graph["control_key_id"],
                )
            )
            ids.append(result.id)
            await session.commit()
        async with graph["session_factory"]() as session:
            repo = SQLAlchemyApiKeyRepository(session)
            saved = await repo.get_by_id(ids[0])
            assert saved.delegation_expires_at == ceiling
            with pytest.raises(AuthorizationError, match="delegation ceiling"):
                await RotateApiKeyUseCase(
                    repo, SimpleNamespace(write=AsyncMock())
                ).execute(
                    RotateApiKeyInput(
                        project_id=graph["project_id"],
                        api_key_id=ids[0],
                        rotated_by_user_id=uuid4(),
                        expires_at=ceiling + timedelta(seconds=1),
                    )
                )
            await session.rollback()
        async with graph["session_factory"]() as session:
            repo = SQLAlchemyApiKeyRepository(session)
            rotated = await RotateApiKeyUseCase(
                repo, SimpleNamespace(write=AsyncMock())
            ).execute(
                RotateApiKeyInput(
                    project_id=graph["project_id"],
                    api_key_id=ids[0],
                    rotated_by_user_id=uuid4(),
                    expires_at=ceiling,
                )
            )
            ids.append(rotated.id)
            await session.commit()
        async with graph["session_factory"]() as session:
            assert (
                await SQLAlchemyApiKeyRepository(session).get_by_id(ids[-1])
            ).delegation_expires_at == ceiling
    finally:
        async with graph["session_factory"]() as session:
            await session.execute(delete(ApiKeyModel).where(ApiKeyModel.id.in_(ids)))
            await session.commit()


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
async def test_project_creator_control_key_receives_explicit_limited_grant(
    control_key_graph,
) -> None:
    graph = control_key_graph
    async with graph["session_factory"]() as session:
        await session.execute(
            text(
                "UPDATE core.workspace_control_keys SET on_project_create_permissions='[\"project:read\"]'::jsonb WHERE id=:id"
            ),
            {"id": graph["control_key_id"]},
        )
        await session.commit()
    principal = ControlPlanePrincipal(
        api_key_id=graph["control_key_id"],
        credential_id=graph["control_key_id"],
        workspace_id=graph["workspace_id"],
        key_prefix="woobe_control_test",
        permissions=frozenset({"workspace:read", "projects:create"}),
        on_project_create_permissions=frozenset({"project:read"}),
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

    assert permissions == {"project:read"}


@pytest.fixture
async def owner_actor(control_key_graph):
    from modules.identity.infra.database.models import UserModel, WorkspaceMemberModel
    from shared.security.principal import AuthenticatedPrincipal

    graph = control_key_graph
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    async with graph["session_factory"]() as session:
        session.add(
            UserModel(
                id=actor.user_id,
                email=f"{actor.user_id}@integration.example",
                password=b"not-a-login",
            )
        )
        await session.flush()
        session.add(
            WorkspaceMemberModel(
                user_id=actor.user_id,
                workspace_id=graph["workspace_id"],
                role="owner",
                joined_at=datetime.now(UTC),
            )
        )
        await session.commit()
    yield actor
    async with graph["session_factory"]() as session:
        await session.execute(
            delete(WorkspaceMemberModel).where(
                WorkspaceMemberModel.user_id == actor.user_id
            )
        )
        await session.execute(delete(UserModel).where(UserModel.id == actor.user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_categories_pin_grants_and_key_revisions_on_postgres(
    control_key_graph, owner_actor
):
    from modules.identity.infra.services.authority_service import AuthorityService
    from shared.contracts.errors import PreconditionFailedError

    graph = control_key_graph
    authority = AuthorityService(graph["session_factory"])
    service = ControlKeyService(graph["session_factory"], authority)
    category = await authority.create_category(
        actor=owner_actor,
        workspace_id=graph["workspace_id"],
        data={
            "name": "ci-editor",
            "scope": "project",
            "permissions": ["agent:read", "agent:write"],
            "conditions": {"environments": ["staging"]},
        },
    )
    created = await service.create_key(
        actor=owner_actor,
        workspace_id=graph["workspace_id"],
        name="Pinned",
        description=None,
        permissions=[],
        project_grants=[
            {
                "project_id": graph["project_id"],
                "category_id": category["id"],
                "category_revision": 1,
            }
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    try:
        assert created["project_grants"][0]["permissions"] == [
            "agent:read",
            "agent:write",
        ]
        await authority.update_category(
            actor=owner_actor,
            workspace_id=graph["workspace_id"],
            category_id=category["id"],
            expected_revision=1,
            changes={
                "permissions": ["agent:read", "agent:production"],
                "conditions": {},
            },
        )
        keys = await service.list_keys(
            actor=owner_actor, workspace_id=graph["workspace_id"]
        )
        pinned = next(key for key in keys if key["id"] == created["id"])
        assert pinned["project_grants"][0]["permissions"] == [
            "agent:read",
            "agent:write",
        ]
        assert pinned["project_grants"][0]["conditions"] == {
            "environments": ["staging"]
        }
        updated = await service.update_key(
            actor=owner_actor,
            workspace_id=graph["workspace_id"],
            control_key_id=created["id"],
            expected_revision=1,
            name="Renamed",
            description=None,
            description_supplied=False,
            permissions=None,
            project_grants=None,
            expires_at=None,
            expires_at_supplied=False,
        )
        assert updated["revision"] == 2
        with pytest.raises(PreconditionFailedError):
            await service.revoke_key(
                actor=owner_actor,
                workspace_id=graph["workspace_id"],
                control_key_id=created["id"],
                expected_revision=1,
            )
        replacement = await service.rotate_key(
            actor=owner_actor,
            workspace_id=graph["workspace_id"],
            control_key_id=created["id"],
            expected_revision=2,
        )
        assert replacement["revision"] == 3
        assert replacement["project_grants"][0]["category_revision"] == 1
        await service.revoke_key(
            actor=owner_actor,
            workspace_id=graph["workspace_id"],
            control_key_id=replacement["id"],
            expected_revision=3,
        )
    finally:
        async with graph["session_factory"]() as session:
            await session.execute(
                text("DELETE FROM core.workspace_control_keys WHERE credential_id=:id"),
                {"id": created["credential_id"]},
            )
            await session.commit()


@pytest.mark.asyncio
async def test_control_delegation_preserves_expiration_and_conditions(
    control_key_graph, owner_actor
):
    graph = control_key_graph
    service = ControlKeyService(graph["session_factory"])
    expiry = datetime.now(UTC) + timedelta(hours=1)
    parent = await service.create_key(
        actor=owner_actor,
        workspace_id=graph["workspace_id"],
        name="Parent",
        description=None,
        permissions=["keys:create", "keys:rotate", "keys:update"],
        project_grants=[
            {
                "project_id": graph["project_id"],
                "permissions": ["agent:read"],
                "conditions": {"environments": ["staging"]},
            }
        ],
        expires_at=expiry,
    )
    actor = ControlPlanePrincipal(
        api_key_id=parent["id"],
        credential_id=parent["credential_id"],
        workspace_id=graph["workspace_id"],
        key_prefix=parent["key_prefix"],
        permissions=frozenset(parent["permissions"]),
        expires_at=expiry,
        on_project_create_permissions=frozenset(
            parent["on_project_create_permissions"]
        ),
        authenticated_at=datetime.now(UTC),
    )
    created_ids = [parent["id"]]
    try:
        for expires in (None, expiry + timedelta(hours=1)):
            with pytest.raises(AuthorizationError, match="ceiling"):
                await service.create_key(
                    actor=actor,
                    workspace_id=graph["workspace_id"],
                    name="Denied expiry",
                    description=None,
                    permissions=[],
                    project_grants=[],
                    expires_at=expires,
                )
        with pytest.raises(AuthorizationError, match="conditions"):
            await service.create_key(
                actor=actor,
                workspace_id=graph["workspace_id"],
                name="Denied production",
                description=None,
                permissions=[],
                project_grants=[
                    {
                        "project_id": graph["project_id"],
                        "permissions": ["agent:read"],
                        "conditions": {},
                    }
                ],
                expires_at=expiry,
            )
        child = await service.create_key(
            actor=actor,
            workspace_id=graph["workspace_id"],
            name="Child",
            description=None,
            permissions=[],
            project_grants=[
                {
                    "project_id": graph["project_id"],
                    "permissions": ["agent:read"],
                    "conditions": {"environments": ["staging"]},
                }
            ],
            expires_at=expiry,
        )
        created_ids.append(child["id"])
        with pytest.raises(AuthorizationError, match="ceiling"):
            await service.rotate_key(
                actor=owner_actor,
                workspace_id=graph["workspace_id"],
                control_key_id=child["id"],
                expected_revision=1,
                expires_at_supplied=True,
                expires_at=None,
            )
    finally:
        async with graph["session_factory"]() as session:
            for key_id in reversed(created_ids):
                await session.execute(
                    text("DELETE FROM core.workspace_control_keys WHERE id=:id"),
                    {"id": key_id},
                )
            await session.commit()


@pytest.mark.asyncio
async def test_project_grant_failure_rolls_back_project_and_outbox(
    control_key_graph, monkeypatch
):
    from unittest.mock import AsyncMock

    graph = control_key_graph
    service = ControlKeyService(graph["session_factory"])
    actor = ControlPlanePrincipal(
        api_key_id=graph["control_key_id"],
        credential_id=graph["control_key_id"],
        workspace_id=graph["workspace_id"],
        key_prefix="woobe_control_test",
        permissions=frozenset({"workspace:read", "projects:create"}),
        authenticated_at=datetime.now(UTC),
    )
    slug = f"atomic-{uuid4()}"
    monkeypatch.setattr(
        service,
        "_grant_created_project",
        AsyncMock(side_effect=RuntimeError("simulated grant persistence failure")),
    )
    with pytest.raises(RuntimeError, match="simulated"):
        await service.create_project_atomically(
            principal=actor,
            payload={
                "workspace_id": graph["workspace_id"],
                "name": "Atomic",
                "slug": slug,
            },
        )
    async with graph["session_factory"]() as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM core.projects WHERE slug=:slug"),
                {"slug": slug},
            )
        ).scalar_one() == 0
        assert (
            await session.execute(
                text(
                    "SELECT count(*) FROM core.outbox_events WHERE payload->>'slug'=:slug"
                ),
                {"slug": slug},
            )
        ).scalar_one() == 0


@pytest.mark.asyncio
async def test_http_control_key_matrix_and_authoritative_preflight(
    control_key_graph, owner_actor, monkeypatch
):
    from httpx import ASGITransport, AsyncClient
    from main import create_app
    from modules.identity.infra.services.authority_service import AuthorityService
    from woobe_api.http.identity import authority_routes
    from woobe_api.http.core import control_key_routes

    graph = control_key_graph
    authority = AuthorityService(graph["session_factory"])
    service = ControlKeyService(graph["session_factory"], authority)
    created = await service.create_key(
        actor=owner_actor,
        workspace_id=graph["workspace_id"],
        name="Reader",
        description=None,
        permissions=["categories:read", "keys:read"],
        project_grants=[
            {
                "project_id": graph["project_id"],
                "permissions": ["project:read", "agent:read", "knowledge:read"],
            }
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    app = create_app()
    app.state.security_guard = _guard(graph["session_factory"], graph["settings"])
    monkeypatch.setattr(authority_routes, "build_authority_service", lambda: authority)
    monkeypatch.setattr(control_key_routes, "_service", lambda: service)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {created['key']}"},
        ) as client:
            cases = [
                ("GET", f"/core/projects/{graph['project_id']}", None, 200),
                ("GET", f"/core/projects/{graph['ungranted_project_id']}", None, 404),
                (
                    "GET",
                    f"/core/projects/{graph['project_id']}?project_id={graph['ungranted_project_id']}",
                    None,
                    409,
                ),
                (
                    "POST",
                    "/ai/agents",
                    {"project_id": str(graph["project_id"]), "name": "denied"},
                    403,
                ),
                (
                    "PATCH",
                    f"/ai/agents/{uuid4()}",
                    {"project_id": str(graph["project_id"])},
                    404,
                ),
                (
                    "POST",
                    "/agent/ai/agents",
                    {"project_id": str(graph["project_id"])},
                    403,
                ),
                ("POST", "/v1/run", {"target": "agent", "input": "denied"}, 403),
                ("GET", "/identity/permissions", None, 200),
                (
                    "GET",
                    f"/identity/access/me?project_id={graph['project_id']}",
                    None,
                    200,
                ),
            ]
            for method, path, body, status in cases:
                response = await client.request(method, path, json=body)
                assert response.status_code == status, (
                    method,
                    path,
                    response.status_code,
                    response.text,
                )
            decision = await client.post(
                "/identity/access/check",
                json={
                    "method": "POST",
                    "path": "/ai/agents",
                    "body": {"project_id": str(graph["project_id"]), "name": "denied"},
                },
            )
            assert decision.status_code == 200
            assert decision.json()["data"]["allowed"] is False
            listed = await client.get(
                f"/core/workspaces/{graph['workspace_id']}/control-keys"
            )
            assert listed.status_code == 200
            assert created["key"] not in listed.text
            assert "key_hash" not in listed.text
    finally:
        async with graph["session_factory"]() as session:
            await session.execute(
                text("DELETE FROM core.workspace_control_keys WHERE id=:id"),
                {"id": created["id"]},
            )
            await session.commit()


@pytest.mark.asyncio
async def test_key_issue_and_rotation_recover_once_on_postgres(
    control_key_graph, owner_actor
):
    import asyncio

    graph = control_key_graph
    service = ControlKeyService(graph["session_factory"])
    key = f"issue-{uuid4()}"
    args = dict(
        actor=owner_actor,
        workspace_id=graph["workspace_id"],
        name="Recoverable",
        description=None,
        permissions=[],
        project_grants=[],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        idempotency_key=key,
    )
    first, second = await asyncio.gather(
        service.create_key(**args), service.create_key(**args)
    )
    assert str(first["id"]) == str(second["id"])
    assert first["key"] == second["key"]
    assert bool(first.get("idempotency_replayed")) != bool(
        second.get("idempotency_replayed")
    )
    try:
        rotate = dict(
            actor=owner_actor,
            workspace_id=graph["workspace_id"],
            control_key_id=UUID(str(first["id"])),
            expected_revision=1,
            idempotency_key=f"rotate-{uuid4()}",
        )
        rotated = await service.rotate_key(**rotate)
        recovered = await service.rotate_key(**rotate)
        assert str(rotated["id"]) == recovered["id"]
        assert rotated["key"] == recovered["key"]
        assert recovered["idempotency_replayed"]
        from shared.contracts.errors import ConflictError

        with pytest.raises(ConflictError):
            await service.create_key(**{**args, "name": "Changed payload"})
    finally:
        async with graph["session_factory"]() as session:
            await session.execute(
                text("DELETE FROM core.workspace_control_keys WHERE credential_id=:id"),
                {"id": UUID(str(first["credential_id"]))},
            )
            await session.commit()
