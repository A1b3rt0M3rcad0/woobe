from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.identity.infra.database.models import (
    UserModel,
    WorkspaceModel,
    WorkspaceMemberModel,
)
from modules.identity.infra.database.authority_models import (
    AuthorityAuditModel,
    AuthorityAssignmentModel,
    AuthorityCategoryModel,
    AuthorityCategoryVersionModel,
)
from modules.identity.infra.services.authority_service import AuthorityService
from shared.contracts.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)
from shared.security.control_plane import (
    CATALOG_REVISION,
    conditions_are_subset,
    expand_permissions,
    require_expiration_ceiling,
    system_profiles,
)
from shared.security.principal import AuthenticatedPrincipal


@pytest_asyncio.fixture
async def authority():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def attach(connection, _):
        connection.execute("ATTACH DATABASE ':memory:' AS identity")
        connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        UserModel.__table__,
        WorkspaceModel.__table__,
        WorkspaceMemberModel.__table__,
        AuthorityCategoryModel.__table__,
        AuthorityCategoryVersionModel.__table__,
        AuthorityAssignmentModel.__table__,
        AuthorityAuditModel.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: UserModel.metadata.create_all(conn, tables=tables)
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    workspace_id = uuid4()
    async with factory() as session:
        session.add_all(
            [
                UserModel(
                    id=actor.user_id,
                    email=f"{actor.user_id}@test.example",
                    password=b"irrelevant",
                ),
                WorkspaceModel(id=workspace_id, name="Test", slug=str(workspace_id)),
            ]
        )
        await session.flush()
        session.add(
            WorkspaceMemberModel(
                user_id=actor.user_id,
                workspace_id=workspace_id,
                role="owner",
                joined_at=datetime.now(UTC),
            )
        )
        await session.commit()
    yield AuthorityService(factory), actor, workspace_id, factory
    await engine.dispose()


def category_data(**changes):
    return {
        "name": "custom-editor",
        "scope": "project",
        "permissions": ["agent:read", "agent:write"],
        "description": "initial",
        **changes,
    }


@pytest.mark.asyncio
async def test_revisions_preserve_materialized_permissions_and_history(authority):
    service, actor, workspace_id, factory = authority
    original = await service.create_category(
        actor=actor, workspace_id=workspace_id, data=category_data()
    )
    updated = await service.update_category(
        actor=actor,
        workspace_id=workspace_id,
        category_id=original["id"],
        expected_revision=1,
        changes={"permissions": ["agent:read"], "description": None},
    )
    assert updated["revision"] == 2
    assert updated["description"] is None
    pinned = await service.get_category(
        actor=actor, workspace_id=workspace_id, category_id=original["id"], revision=1
    )
    assert pinned["permissions"] == ["agent:read", "agent:write"]
    assert pinned["description"] == "initial"
    history = await service.category_history(
        actor=actor, workspace_id=workspace_id, category_id=original["id"], limit=1
    )
    assert [item["revision"] for item in history["items"]] == [2]
    assert history["next_revision"] == 2
    page = await service.category_history(
        actor=actor,
        workspace_id=workspace_id,
        category_id=original["id"],
        before_revision=2,
    )
    assert [item["revision"] for item in page["items"]] == [1]
    async with factory() as session:
        audits = list((await session.execute(select(AuthorityAuditModel))).scalars())
        assert [a.operation for a in audits] == ["category.create", "category.update"]
        assert all(
            a.actor_user_id == actor.user_id and a.actor_control_key_id is None
            for a in audits
        )


@pytest.mark.asyncio
async def test_stale_revision_cannot_overwrite_or_archive(authority):
    service, actor, workspace_id, _ = authority
    original = await service.create_category(
        actor=actor, workspace_id=workspace_id, data=category_data()
    )
    await service.update_category(
        actor=actor,
        workspace_id=workspace_id,
        category_id=original["id"],
        expected_revision=1,
        changes={"name": "changed"},
    )
    for archive in (True, False):
        with pytest.raises(PreconditionFailedError):
            await service.update_category(
                actor=actor,
                workspace_id=workspace_id,
                category_id=original["id"],
                expected_revision=1,
                changes={"permissions": []},
                archive=archive,
            )
    assert (
        await service.get_category(
            actor=actor, workspace_id=workspace_id, category_id=original["id"]
        )
    )["permissions"] == ["agent:read", "agent:write"]


@pytest.mark.asyncio
async def test_archive_preserves_history_and_prevents_new_grants(authority):
    service, actor, workspace_id, factory = authority
    original = await service.create_category(
        actor=actor, workspace_id=workspace_id, data=category_data()
    )
    with pytest.raises(ConflictError, match="Archive"):
        await service.delete_category(
            actor=actor,
            workspace_id=workspace_id,
            category_id=original["id"],
            expected_revision=1,
        )
    archived = await service.update_category(
        actor=actor,
        workspace_id=workspace_id,
        category_id=original["id"],
        expected_revision=1,
        changes={},
        archive=True,
    )
    assert archived["status"] == "archived"
    async with factory() as session:
        with pytest.raises(ConflictError, match="archived"):
            await service.resolve_category(
                workspace_id=workspace_id,
                category_id=original["id"],
                revision=1,
                scope="project",
                transaction=session,
            )
    await service.delete_category(
        actor=actor,
        workspace_id=workspace_id,
        category_id=original["id"],
        expected_revision=2,
    )
    with pytest.raises(NotFoundError):
        await service.get_category(
            actor=actor, workspace_id=workspace_id, category_id=original["id"]
        )


@pytest.mark.asyncio
async def test_system_profiles_are_workspace_specific_and_immutable(authority):
    service, actor, workspace_id, factory = authority
    result = await service.list_categories(actor=actor, workspace_id=workspace_id)
    profile = next(
        item for item in result["system_categories"] if item["name"] == "agent-editor"
    )
    assert profile["permissions"] == ["agent:read", "agent:write"]
    with pytest.raises(ConflictError, match="immutable"):
        await service.update_category(
            actor=actor,
            workspace_id=workspace_id,
            category_id=profile["id"],
            expected_revision=1,
            changes={},
        )
    async with factory() as session:
        pinned = await service.resolve_category(
            workspace_id=workspace_id,
            category_id=profile["id"],
            revision=1,
            scope="project",
            transaction=session,
        )
        await session.commit()
    assert pinned["system"]
    assert service._profile_id(uuid4(), "agent-editor") != profile["id"]
    with pytest.raises(ConflictError):
        await service.create_category(
            actor=actor,
            workspace_id=workspace_id,
            data=category_data(name="agent-editor"),
        )


@pytest.mark.asyncio
async def test_workspace_isolation_and_duplicate_names(authority):
    service, actor, workspace_id, _ = authority
    result = await service.create_category(
        actor=actor, workspace_id=workspace_id, data=category_data()
    )
    with pytest.raises(ConflictError):
        await service.create_category(
            actor=actor, workspace_id=workspace_id, data=category_data()
        )
    with pytest.raises(NotFoundError):
        await service.get_category(
            actor=actor, workspace_id=uuid4(), category_id=result["id"]
        )


@pytest.mark.parametrize(
    "data",
    [
        category_data(name="../bad"),
        category_data(permissions=["future:write"]),
        category_data(
            scope="workspace",
            permissions=["keys:read"],
            conditions={"environments": ["production"]},
        ),
        category_data(conditions={"environments": ["draft"]}),
        category_data(permissions=["agent:*"]),
    ],
)
@pytest.mark.asyncio
async def test_invalid_categories_do_not_persist(authority, data):
    service, actor, workspace_id, _ = authority
    with pytest.raises(ValidationError):
        await service.create_category(actor=actor, workspace_id=workspace_id, data=data)
    assert (await service.list_categories(actor=actor, workspace_id=workspace_id))[
        "items"
    ] == []


@pytest.mark.parametrize(
    "requested, available, expected",
    [
        ({}, {}, True),
        ({}, {"environments": ["staging"]}, False),
        (
            {"environments": ["staging"]},
            {"environments": ["staging", "production"]},
            True,
        ),
        ({"environments": ["production"]}, {"environments": ["staging"]}, False),
        ({"target_ids": []}, {"target_ids": [str(uuid4())]}, True),
        ({"interfaces": ["http", "stream"]}, {"interfaces": ["http"]}, False),
    ],
)
def test_conditions_cannot_broaden_parent(requested, available, expected):
    assert conditions_are_subset(requested, available) is expected


def test_wildcards_expand_only_finite_versioned_catalog():
    expanded = expand_permissions(
        ["agent:*"], scope="project", catalog_revision=CATALOG_REVISION
    )
    assert expanded == [
        "agent:delete",
        "agent:production",
        "agent:read",
        "agent:version",
        "agent:write",
    ]
    with pytest.raises(ValueError):
        expand_permissions(["*"], scope="project", catalog_revision="old")
    assert "agent:production" not in system_profiles()["agent-editor"][1]


@pytest.mark.parametrize("offset", [None, 3])
def test_delegated_expiration_cannot_be_removed_or_extended(offset):
    ceiling = datetime.now(UTC) + timedelta(days=2)
    expiry = datetime.now(UTC) + timedelta(days=offset) if offset else None
    with pytest.raises(ValueError, match="ceiling"):
        require_expiration_ceiling(expiry, ceiling)
    require_expiration_ceiling(ceiling - timedelta(hours=1), ceiling)


@pytest.mark.parametrize(
    "permission",
    [
        "agent:write",
        "agent:version",
        "agent:production",
        "network:production",
        "tool:execute",
        "keys:create",
        "project:environment:write",
    ],
)
@pytest.mark.asyncio
async def test_viewer_role_denies_every_mutation_family(permission):
    from unittest.mock import AsyncMock
    from shared.security.tenancy import TenantAuthorizer

    authorizer = TenantAuthorizer(object())
    authorizer._workspace_role = AsyncMock(return_value="viewer")
    with pytest.raises(AuthorizationError, match="read-only"):
        await authorizer.require_human_permission(
            user_id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
            permission=permission,
        )


@pytest.mark.parametrize(
    "conditions,permission,body,path",
    [
        (
            {"environments": ["staging"]},
            "agent:production",
            {},
            {"agent_id": str(uuid4())},
        ),
        ({"target_ids": [str(uuid4())]}, "agent:read", {}, {}),
        (
            {"target_types": ["agent"]},
            "network:write",
            {},
            {"network_id": str(uuid4())},
        ),
        ({"interfaces": []}, "agent:read", {}, {"agent_id": str(uuid4())}),
    ],
)
def test_missing_or_out_of_scope_conditions_fail_closed(
    conditions, permission, body, path
):
    from shared.security.tenancy import TenantAuthorizer

    with pytest.raises(AuthorizationError):
        TenantAuthorizer._require_conditions(
            conditions, permission=permission, context=body, path_context=path
        )


@pytest.mark.parametrize(
    "permission",
    ["agent:read", "agent:write", "network:read", "network:write", "run:execute"],
)
def test_body_target_cannot_bypass_a_target_restricted_collection(permission):
    from shared.security.tenancy import TenantAuthorizer

    target_id = str(uuid4())
    with pytest.raises(AuthorizationError, match="explicit target"):
        TenantAuthorizer._require_conditions(
            {"target_ids": [target_id]},
            permission=permission,
            context={
                "agent_id": target_id,
                "network_id": target_id,
                "target_id": target_id,
            },
            path_context={},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested,allowed",
    [
        ({}, {"environments": ["staging"]}),
        ({"environments": ["production"]}, {"environments": ["staging"]}),
    ],
)
async def test_human_delegation_cannot_remove_or_broaden_assigned_conditions(
    requested, allowed
):
    from unittest.mock import AsyncMock, Mock
    from shared.security.tenancy import TenantAuthorizer

    result = Mock()
    result.first.return_value = (["agent:read"], allowed)
    authorizer = TenantAuthorizer(
        SimpleNamespace(execute=AsyncMock(return_value=result))
    )
    authorizer._workspace_role = AsyncMock(return_value="member")
    authorizer._require_project_access = AsyncMock()
    with pytest.raises(AuthorizationError, match="broaden assigned conditions"):
        await authorizer.require_human_permission(
            user_id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
            permission="agent:read",
            delegated_conditions=requested,
        )


@pytest.mark.asyncio
async def test_renaming_preserves_historical_category_name(authority):
    service, actor, workspace_id, _ = authority
    created = await service.create_category(
        actor=actor, workspace_id=workspace_id, data=category_data()
    )
    await service.update_category(
        actor=actor,
        workspace_id=workspace_id,
        category_id=created["id"],
        expected_revision=1,
        changes={"name": "renamed"},
    )
    assert (
        await service.get_category(
            actor=actor,
            workspace_id=workspace_id,
            category_id=created["id"],
            revision=1,
        )
    )["name"] == "custom-editor"
