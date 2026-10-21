from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.domain.entities import NetworkArtifactWorkspaceBinding
from modules.network.infra.services.service import NetworkApplicationService
from shared.infra.errors import AuthorizationError, ConflictError, ValidationError
from shared.security.principal import ProjectApiPrincipal


def _service(binding):
    service = object.__new__(NetworkApplicationService)

    async def resolve(**kwargs):
        service.resolver_request = kwargs
        return SimpleNamespace(
            workspace_id=binding["workspace_id"],
            catalog_version=binding.get("catalog_version", 13),
            actions=binding.get("actions", ("read", "search")),
        )

    service._artifact_workspace_binding_resolver = resolve
    return service


def _principal():
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="runtime",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type="network",
        target_id=uuid4(),
        environment="staging",
        interfaces=frozenset({"network", "artifacts"}),
        authenticated_at=datetime.now(UTC),
    )


def _definition(scope="session"):
    return SimpleNamespace(
        artifacts_enabled=True,
        artifact_workspace_binding=NetworkArtifactWorkspaceBinding(
            field="workspace_key",
            namespace="customer-documents",
            scope=scope,
            actions=("read", "search"),
        ),
    )


def _contract(scope="session"):
    return {
        "workspace_key": {
            "schema": {"type": "string"},
            "scope": scope,
            "consumers": {
                "node-a": {"required": True, "model": {"expose": False}},
            },
        }
    }


@pytest.mark.asyncio
async def test_network_acceptance_resolves_logical_workspace_and_freezes_private_snapshot():
    service = _service({"workspace_id": "workspace-root"})
    session = SimpleNamespace(
        environment="staging",
        artifact_workspace_binding=None,
        last_message_at=None,
    )
    principal = _principal()

    binding, principal_snapshot = await service._resolve_artifact_workspace_binding(
        network_session=session,
        definition=_definition(),
        project_id=principal.project_id,
        principal=principal,
        external_context_contract=_contract(),
        external_context_snapshot={"workspace_key": "customer-42"},
    )

    assert service.resolver_request == {
        "principal": principal,
        "project_id": principal.project_id,
        "environment": "staging",
        "external_namespace": "customer-documents",
        "external_key": "customer-42",
        "actions": ("read", "search"),
        "binding_scope": "session",
    }
    assert binding == {
        "schema_version": 1,
        "workspace_id": "workspace-root",
        "catalog_version": 13,
        "binding_scope": "session",
        "actions": ["read", "search"],
    }
    assert session.artifact_workspace_binding == binding
    assert principal_snapshot["api_key_id"] == str(principal.api_key_id)
    assert "secret" not in principal_snapshot


@pytest.mark.asyncio
async def test_network_session_allows_identical_replay_but_rejects_workspace_switch():
    service = _service({"workspace_id": "workspace-root"})
    principal = _principal()
    session = SimpleNamespace(
        environment="staging",
        artifact_workspace_binding={"workspace_id": "workspace-root"},
        last_message_at=datetime.now(UTC),
    )
    await service._resolve_artifact_workspace_binding(
        network_session=session,
        definition=_definition(),
        project_id=principal.project_id,
        principal=principal,
        external_context_contract=_contract(),
        external_context_snapshot={"workspace_key": "customer-42"},
    )

    other = _service({"workspace_id": "workspace-other"})
    with pytest.raises(ConflictError, match="cannot switch Artifact Workspaces"):
        await other._resolve_artifact_workspace_binding(
            network_session=session,
            definition=_definition("run"),
            project_id=principal.project_id,
            principal=principal,
            external_context_contract=_contract("run"),
            external_context_snapshot={"workspace_key": "customer-43"},
        )


@pytest.mark.asyncio
async def test_network_session_keeps_first_accepted_catalog_snapshot():
    service = _service({"workspace_id": "workspace-root", "catalog_version": 21})
    session = SimpleNamespace(
        environment="staging",
        artifact_workspace_binding={
            "workspace_id": "workspace-root", "catalog_version": 13, "binding_scope": "session",
        },
        last_message_at=datetime.now(UTC),
    )

    binding, _ = await service._resolve_artifact_workspace_binding(
        network_session=session,
        definition=_definition(),
        project_id=_principal().project_id,
        principal=_principal(),
        external_context_contract=_contract(),
        external_context_snapshot={"workspace_key": "customer-42"},
    )

    assert binding["catalog_version"] == 13
    assert session.artifact_workspace_binding["catalog_version"] == 13


@pytest.mark.asyncio
async def test_network_artifact_acceptance_requires_principal_and_hidden_required_field():
    service = _service({"workspace_id": "workspace-root"})
    session = SimpleNamespace(environment="staging", artifact_workspace_binding=None, last_message_at=None)
    with pytest.raises(AuthorizationError, match="authenticated principal"):
        await service._resolve_artifact_workspace_binding(
            network_session=session,
            definition=_definition(),
            project_id=uuid4(),
            principal=None,
            external_context_contract=_contract(),
            external_context_snapshot={"workspace_key": "customer-42"},
        )

    principal = _principal()
    exposed = _contract()
    exposed["workspace_key"]["consumers"]["node-a"]["model"]["expose"] = True
    with pytest.raises(ValidationError, match="required, hidden"):
        await service._resolve_artifact_workspace_binding(
            network_session=session,
            definition=_definition(),
            project_id=principal.project_id,
            principal=principal,
            external_context_contract=exposed,
            external_context_snapshot={"workspace_key": "customer-42"},
        )
