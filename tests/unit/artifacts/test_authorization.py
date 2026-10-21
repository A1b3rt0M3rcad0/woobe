from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from modules.artifacts.application.authorization import (
    ArtifactAuthorization,
    principal_identity,
)
from modules.artifacts.domain.models import (
    Action,
    ArtifactError,
    Scope,
    Workspace,
    WorkspaceGrant,
)
from shared.contracts.errors import AuthenticationError
from shared.security.principal import ProjectApiPrincipal
from woobe_api.security.http_guard import (
    is_runtime_execution_request,
    is_runtime_path,
    public_runtime_interface,
)


class AuthorityDouble:
    def __init__(self):
        self.revoked = False
        self.calls = 0

    async def require(self, principal, scope, action):
        self.calls += 1
        if self.revoked:
            raise AuthenticationError("revoked")


class GrantReaderDouble:
    def __init__(self, workspace, grant):
        self.value = workspace
        self.grants = (grant,)

    async def workspace(self, scope, workspace_id):
        if self.value.scope != scope or self.value.id != workspace_id:
            raise ArtifactError("SOURCE_UNAVAILABLE", "unavailable")
        return self.value

    async def current(self, principal_id, scope):
        return tuple(
            g
            for g in self.grants
            if g.principal_id == principal_id and g.scope == scope
        )


def fixture():
    project_id = uuid4()
    actor = ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=project_id,
        key_prefix="test",
        kind="runtime",
        target_type="agent",
        target_id=uuid4(),
        environment="staging",
        interfaces=frozenset({"artifacts"}),
        scopes=frozenset({"runtime:execute"}),
        authenticated_at=datetime.now(UTC),
    )
    workspace = Workspace(
        "workspace", Scope(str(project_id), "staging"), "app", "external", "Files"
    )
    grant = WorkspaceGrant(
        "grant",
        principal_identity(actor),
        workspace.scope,
        frozenset({Action.READ, Action.SEARCH}),
        workspace_id=workspace.id,
    )
    authority = AuthorityDouble()
    reader = GrantReaderDouble(workspace, grant)
    return (
        actor,
        workspace,
        grant,
        authority,
        reader,
        ArtifactAuthorization(authority, reader),
    )


@pytest.mark.parametrize(
    "action,allowed", [(a, a in {Action.READ, Action.SEARCH}) for a in Action]
)
async def test_operation_intersection_denies_by_default(action, allowed):
    actor, ws, grant, authority, reader, access = fixture()
    if allowed:
        assert await access.authorize(actor, ws.scope, ws.id, action) == ws
    else:
        with pytest.raises(ArtifactError) as error:
            await access.authorize(actor, ws.scope, ws.id, action)
        assert error.value.code == "ARTIFACT_ACCESS_DENIED"


@pytest.mark.parametrize(
    "mutation",
    [
        "interface",
        "project",
        "environment",
        "kind",
        "expired",
        "revoked",
        "missing",
        "workspace",
    ],
)
async def test_selection_and_retained_grants_do_not_confer_authority(mutation):
    actor, ws, grant, authority, reader, access = fixture()
    workspace_id = ws.id
    if mutation == "interface":
        actor = actor.model_copy(update={"interfaces": frozenset({"http"})})
    if mutation == "project":
        actor = actor.model_copy(update={"project_id": uuid4()})
    if mutation == "environment":
        actor = actor.model_copy(update={"environment": "production"})
    if mutation == "kind":
        actor = actor.model_copy(update={"kind": "project"})
    if mutation == "expired":
        reader.grants = (
            replace(grant, expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        )
    if mutation == "revoked":
        reader.grants = (replace(grant, revoked=True),)
    if mutation == "missing":
        reader.grants = ()
    if mutation == "workspace":
        workspace_id = "other-workspace"
    with pytest.raises(ArtifactError) as error:
        await access.authorize(actor, ws.scope, workspace_id, Action.READ)
    assert error.value.code == "ARTIFACT_ACCESS_DENIED"


async def test_revocation_is_rechecked_between_admission_and_later_operations():
    actor, ws, grant, authority, reader, access = fixture()
    await access.authorize(actor, ws.scope, ws.id, Action.READ)
    authority.revoked = True
    with pytest.raises(ArtifactError):
        await access.authorize(actor, ws.scope, ws.id, Action.READ)
    assert authority.calls == 2
    authority.revoked = False
    reader.grants = (replace(grant, revoked=True),)
    with pytest.raises(ArtifactError):
        await access.authorize(actor, ws.scope, ws.id, Action.READ)


async def test_release_node_and_bound_workspace_only_reduce_access():
    actor, ws, grant, authority, reader, access = fixture()
    for limits in (
        {"release_actions": frozenset()},
        {"node_actions": frozenset()},
        {"workspace_limit": "other"},
    ):
        with pytest.raises(ArtifactError):
            await access.authorize(actor, ws.scope, ws.id, Action.READ, **limits)
    reader.grants = (
        replace(grant, workspace_id=None, external_namespace=ws.external_namespace),
    )
    await access.authorize(actor, ws.scope, ws.id, Action.READ)
    with pytest.raises(ArtifactError):
        await access.authorize_namespace(actor, ws.scope, "other", Action.READ)


def test_artifact_interface_does_not_become_run_execution_or_generic_jobs():
    for path in (
        "/v1/artifact-workspaces",
        "/v1/artifact-workspaces/ws/uploads/id/parts",
        "/v1/artifacts/a/revisions/r/content",
        "/v1/source-references/resolve",
    ):
        assert is_runtime_path(path)
        assert public_runtime_interface("POST", path) == "artifacts"
        assert not is_runtime_execution_request("POST", path)
    assert public_runtime_interface("POST", "/v1/jobs") == "jobs"
    assert public_runtime_interface("POST", "/v1/artifact-workspaces-evil") is None


@pytest.mark.parametrize('status,action,allowed', [
    ('archived', Action.READ, True), ('archived', Action.WRITE, False),
    ('deletion_pending', Action.READ, False), ('deletion_pending', Action.MANAGE, True),
])
async def test_lifecycle_blocks_data_operations_but_allows_authorized_management(status, action, allowed):
    actor, ws, grant, authority, reader, access = fixture()
    reader.value = replace(ws, status=status)
    reader.grants = (replace(grant, actions=frozenset(Action)),)
    if allowed:
        await access.authorize(actor, ws.scope, ws.id, action)
    else:
        with pytest.raises(ArtifactError):
            await access.authorize(actor, ws.scope, ws.id, action)
