from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    RequestExecutionContext,
    current_execution,
)
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.artifacts.domain.models import Action, Environment, RuntimeArtifactBinding, Scope
from shared.contracts.errors import AuthorizationError, ConflictError, ValidationError
from shared.presentation.contracts import OperationOutcome, OperationRequest
from shared.security.principal import AuthenticatedPrincipal


def _agent(*, scope="session"):
    return SimpleNamespace(
        settings={
            "external_context_contract": {
                "workspace": {
                    "schema": {"type": "string"},
                    "required": True,
                    "scope": scope,
                    "model": {"expose": False},
                }
            },
            "runtime_config": {
                "artifacts": {
                    "enabled": True,
                    "workspace_binding": {
                        "field": "workspace",
                        "namespace": "team-docs",
                        "scope": scope,
                    },
                    "actions": ["read", "search"],
                }
            },
        }
    )


def _principal():
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now.replace(year=now.year + 1),
    )


def _resolver(binding):
    resolver = object.__new__(ReleaseRuntimeResolver)

    async def resolve(**kwargs):
        resolver.last_request = kwargs
        return binding

    resolver.configure_artifact_workspace_binding_resolver(resolve)
    return resolver


def _binding(workspace_id="workspace-a", catalog_version=7):
    return RuntimeArtifactBinding(
        workspace_id=workspace_id,
        scope=Scope(str(uuid4()), Environment.STAGING),
        catalog_version=catalog_version,
        actions=frozenset({Action.READ, Action.SEARCH}),
        binding_scope="session",
    )


@pytest.mark.asyncio
async def test_acceptance_resolves_logical_key_by_project_environment_and_grants():
    resolver = _resolver(_binding())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="summarize",
        external_context={"workspace": "quarterly-report"},
        execution_context="staging",
        runtime_principal=_principal(),
    )
    session = SimpleNamespace(
        external_context_snapshot=None,
        artifact_workspace_binding=None,
        last_message_at=None,
    )
    context = RequestExecutionContext(
        started_at=0.0,
        request_received_at="now",
        execution_started_at="now",
    )
    token = current_execution.set(context)
    try:
        await resolver._resolve_external_context(
            agent=_agent(), input_dto=input_dto, session=session
        )
    finally:
        current_execution.reset(token)

    request = resolver.last_request
    assert request["principal"] is input_dto.runtime_principal
    assert request["project_id"] == input_dto.project_id
    assert request["environment"] == "staging"
    assert request["external_namespace"] == "team-docs"
    assert request["external_key"] == "quarterly-report"
    assert request["actions"] == ("read", "search")
    assert context.artifact_workspace_binding.workspace_id == "workspace-a"
    assert context.artifact_workspace_binding.catalog_version == 7
    assert context.model_external_context is None
    assert session.artifact_workspace_binding["workspace_id"] == "workspace-a"
    assert "runtime_principal" not in input_dto.model_dump()


@pytest.mark.asyncio
async def test_enabled_artifacts_fail_before_provider_without_principal_or_resolver():
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="summarize",
        external_context={"workspace": "quarterly-report"},
    )
    with pytest.raises(AuthorizationError, match="access is denied"):
        await _resolver(_binding())._resolve_external_context(
            agent=_agent(), input_dto=input_dto
        )

    resolver = object.__new__(ReleaseRuntimeResolver)
    input_dto.runtime_principal = _principal()
    with pytest.raises(ValidationError, match="resolver is unavailable"):
        await resolver._resolve_external_context(agent=_agent(), input_dto=input_dto)


@pytest.mark.asyncio
async def test_stateful_session_with_history_cannot_switch_run_scoped_workspace():
    resolver = _resolver(_binding("workspace-b"))
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="continue",
        external_context={"workspace": "another-report"},
        runtime_principal=_principal(),
    )
    agent = _agent(scope="run")
    session = SimpleNamespace(
        external_context_snapshot=None,
        artifact_workspace_binding={
            "workspace_id": "workspace-a",
            "binding_scope": "run",
        },
        last_message_at=datetime.now(UTC),
    )
    with pytest.raises(ConflictError, match="cannot switch Artifact Workspaces"):
        await resolver._resolve_external_context(
            agent=agent, input_dto=input_dto, session=session
        )


@pytest.mark.asyncio
async def test_session_scoped_external_context_replay_rejects_a_different_workspace_key():
    resolver = _resolver(_binding("workspace-b"))
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="continue",
        external_context={"workspace": "another-report"},
        runtime_principal=_principal(),
    )
    session = SimpleNamespace(
        external_context_snapshot={"workspace": "quarterly-report"},
        artifact_workspace_binding={"workspace_id": "workspace-a"},
        last_message_at=datetime.now(UTC),
    )
    with pytest.raises(ConflictError):
        await resolver._resolve_external_context(
            agent=_agent(), input_dto=input_dto, session=session
        )


@pytest.mark.asyncio
async def test_session_binding_keeps_accepted_catalog_while_rechecking_the_resolver():
    resolver = _resolver(_binding(catalog_version=9))
    input_dto = AskInput(
        project_id=uuid4(), agent_id=uuid4(), message="continue",
        external_context={"workspace": "quarterly-report"}, runtime_principal=_principal(),
    )
    session = SimpleNamespace(
        external_context_snapshot=None,
        artifact_workspace_binding={
            "workspace_id": "workspace-a", "catalog_version": 7, "binding_scope": "session",
        },
        last_message_at=datetime.now(UTC),
    )
    context = RequestExecutionContext(
        started_at=0.0, request_received_at="now", execution_started_at="now",
    )
    token = current_execution.set(context)
    try:
        await resolver._resolve_external_context(agent=_agent(), input_dto=input_dto, session=session)
    finally:
        current_execution.reset(token)

    assert resolver.last_request["external_key"] == "quarterly-report"
    assert context.artifact_workspace_binding.catalog_version == 7
    assert session.artifact_workspace_binding["catalog_version"] == 7


@pytest.mark.asyncio
async def test_ask_controller_uses_authenticated_principal_and_returns_forbidden():
    from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController

    principal = _principal()

    class _DeniedUseCase:
        async def execute(self, input_dto):
            assert input_dto.runtime_principal is principal
            assert "__network_artifact_runtime__" not in input_dto.metadata
            assert input_dto.metadata.get("source") != "network_runtime"
            raise AuthorizationError("Artifact Workspace access is denied")

    response = await AskAgentController(_DeniedUseCase()).handle(
        OperationRequest(
            principal=principal,
            body={
                "project_id": str(uuid4()),
                "agent_id": str(uuid4()),
                "message": "read",
                "runtime_principal": "untrusted body value",
                "metadata": {
                    "source": "network_runtime",
                    "__network_artifact_runtime__": {
                        "enabled": True,
                        "binding": {"workspace_id": "attacker-selected"},
                    },
                },
            },
        )
    )
    assert response.outcome == OperationOutcome.FORBIDDEN


@pytest.mark.asyncio
async def test_network_node_actions_intersect_network_and_agent_release_policies():
    resolver = _resolver(_binding())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="read a chapter",
        external_context={"workspace": "quarterly-report"},
        runtime_principal=_principal(),
        metadata={
            "source": "network_runtime",
            "__network_artifact_runtime__": {
                "enabled": True,
                "binding": {"workspace_id": "workspace-a", "catalog_version": 7},
                "policy": {
                    "field": "workspace",
                    "namespace": "team-docs",
                    "scope": "session",
                    "actions": ["read", "search", "write"],
                },
                "node_actions": ["read", "write"],
            },
        },
    )
    context = RequestExecutionContext(
        started_at=0.0,
        request_received_at="now",
        execution_started_at="now",
    )
    token = current_execution.set(context)
    try:
        await resolver._resolve_external_context(agent=_agent(), input_dto=input_dto)
    finally:
        current_execution.reset(token)

    assert resolver.last_request["actions"] == ("read",)
    assert context.artifact_workspace_binding.workspace_id == "workspace-a"


@pytest.mark.asyncio
async def test_agent_capability_cannot_enable_artifacts_when_network_policy_is_off():
    resolver = _resolver(_binding())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="list files",
        external_context={"workspace": "quarterly-report"},
        runtime_principal=_principal(),
        metadata={
            "source": "network_runtime",
            "__network_artifact_runtime__": {"enabled": False},
        },
    )
    context = RequestExecutionContext(
        started_at=0.0,
        request_received_at="now",
        execution_started_at="now",
    )
    token = current_execution.set(context)
    try:
        await resolver._resolve_external_context(agent=_agent(), input_dto=input_dto)
    finally:
        current_execution.reset(token)

    assert not hasattr(resolver, "last_request")
    assert context.artifact_workspace_binding is None
