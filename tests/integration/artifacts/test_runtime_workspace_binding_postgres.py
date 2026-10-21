from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from modules.agent.infra.database.models import AgentModel, SessionModel
from modules.agent.infra.database.runtime_session_repository import (
    SQLAlchemyRuntimeSessionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.artifacts.domain.models import Action, ArtifactError, Environment, Scope, Workspace
from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.infra.database.authorization import GrantRepository
from modules.artifacts.infra.database.models import GrantModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.security.principal import AuthenticatedPrincipal


class _TestAuthority:
    async def require(self, _principal, _scope, _action):
        return None


@pytest.mark.asyncio
async def test_acceptance_binds_logical_workspace_and_rechecks_current_grants(
    artifacts_database, engine, monkeypatch
):
    from modules.artifacts.composition import runtime_binding

    monkeypatch.setattr(runtime_binding, "DATABASE_ENGINE", engine)
    monkeypatch.setattr(
        runtime_binding, "ExistingPrincipalAuthority", lambda _uow: _TestAuthority()
    )

    project_id = UUID(artifacts_database["project_id"])
    user_id = uuid4()
    principal = AuthenticatedPrincipal(
        user_id=user_id,
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    scope = Scope(str(project_id), Environment.STAGING)
    workspace = Workspace(
        id="acceptance-workspace-1",
        scope=scope,
        external_namespace="team-docs",
        external_key="quarterly-report",
        name="Quarterly report",
        catalog_version=11,
    )
    grant_id = uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        from modules.artifacts.infra.database.catalog import CatalogRepository

        await CatalogRepository(uow).insert_workspace(workspace)
        uow.session.add(
            GrantModel(
                id=str(grant_id),
                project_id=project_id,
                environment=scope.environment.value,
                principal_id=f"user-{user_id}",
                workspace_id=workspace.id,
                external_namespace=None,
                actions=[Action.READ.value, Action.SEARCH.value],
                revision=1,
                revoked=False,
            )
        )

    binding = await runtime_binding.resolve_runtime_artifact_workspace_binding(
        principal=principal,
        project_id=project_id,
        environment="staging",
        external_namespace="team-docs",
        external_key="quarterly-report",
        actions=("read", "search"),
        binding_scope="session",
    )
    assert binding.workspace_id == workspace.id
    assert binding.catalog_version == 11
    assert binding.actions == frozenset({Action.READ, Action.SEARCH})

    async with ArtifactsUnitOfWork(engine) as uow:
        grant = await uow.session.scalar(
            select(GrantModel).where(GrantModel.id == str(grant_id))
        )
        grant.revoked = True
        grant.revision += 1

    with pytest.raises(ArtifactError) as denied:
        await runtime_binding.resolve_runtime_artifact_workspace_binding(
            principal=principal,
            project_id=project_id,
            environment="staging",
            external_namespace="team-docs",
            external_key="quarterly-report",
            actions=("read",),
            binding_scope="session",
        )
    assert denied.value.code == "ARTIFACT_ACCESS_DENIED"

    with pytest.raises(ArtifactError) as hidden:
        await runtime_binding.resolve_runtime_artifact_workspace_binding(
            principal=principal,
            project_id=project_id,
            environment="production",
            external_namespace="team-docs",
            external_key="quarterly-report",
            actions=("read",),
            binding_scope="session",
        )
    assert hidden.value.code == "ARTIFACT_ACCESS_DENIED"

    agent_id, session_id = uuid4(), uuid4()
    binding_snapshot = {
        "schema_version": 1,
        "workspace_id": workspace.id,
        "catalog_version": 11,
        "binding_scope": "session",
        "actions": ["read", "search"],
    }
    async with ArtifactsUnitOfWork(engine) as uow:
        uow.session.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=None,
                fallback_credential_id=None,
                name="Workspace binding test Agent",
                description="",
                type="assistant",
                system_prompt="",
                provider="openai",
                model="test-model",
                fallback_provider=None,
                fallback_model=None,
                temperature=0,
                max_output_tokens=32,
                session_mode="stateful",
                status="active",
                settings={},
            )
        )
        await uow.session.flush()
        uow.session.add(
            SessionModel(
                id=session_id,
                project_id=project_id,
                agent_id=agent_id,
                runtime_environment="staging",
                opened_release_id=None,
                chat_surface_id=None,
                origin="runtime_api",
                external_session_id=None,
                tenant_id=None,
                user_id=None,
                status="active",
                mode="chat",
                data=None,
                external_context_snapshot={"workspace": "quarterly-report"},
                artifact_workspace_binding=binding_snapshot,
                last_message_at=None,
            )
        )

    async with AgentUnitOfWork(engine) as uow:
        session = await SQLAlchemyRuntimeSessionRepository(uow).get_by_id_for_update(
            session_id
        )
        assert session.artifact_workspace_binding == binding_snapshot


@pytest.mark.asyncio
async def test_network_workspace_and_principal_snapshots_roundtrip_after_migration(
    artifacts_database, engine
):
    from modules.network.infra.database.models import (
        NetworkExecutionModel,
        NetworkModel,
        NetworkSessionModel,
    )
    from modules.network.infra.runtime.loader import NetworkRuntimeLoader

    project_id = UUID(artifacts_database["project_id"])
    network_id, session_id, execution_id = uuid4(), uuid4(), uuid4()
    binding = {
        "schema_version": 1,
        "workspace_id": "network-workspace-1",
        "catalog_version": 27,
        "binding_scope": "session",
        "actions": ["read", "search"],
    }
    principal_snapshot = {
        "kind": "runtime",
        "project_id": str(project_id),
        "interfaces": ["network", "artifacts"],
    }
    async with ArtifactsUnitOfWork(engine) as uow:
        uow.session.add(
            NetworkModel(
                id=network_id,
                project_id=project_id,
                name="Artifact binding roundtrip",
                description="",
                draft_definition={"nodes": [], "edges": []},
                draft_revision=1,
                staging_version_id=None,
                production_version_id=None,
            )
        )
        await uow.session.flush()
        uow.session.add(
            NetworkSessionModel(
                id=session_id,
                network_id=network_id,
                network_version_id=None,
                project_id=project_id,
                environment="draft",
                title="Artifact binding session",
                status="active",
                artifact_workspace_binding=binding,
            )
        )
        await uow.session.flush()
        uow.session.add(
            NetworkExecutionModel(
                id=execution_id,
                network_id=network_id,
                network_session_id=session_id,
                network_version_id=None,
                project_id=project_id,
                input_message="run",
                input_content_parts=[
                    {
                        "type": "artifact",
                        "ref": {
                            "artifact_id": "report-1",
                            "revision_id": "report-revision-3",
                        },
                        "media_type_hint": "application/pdf",
                    }
                ],
                draft_revision=1,
                definition_snapshot={"nodes": [], "edges": []},
                resolved_bindings_snapshot={},
                artifact_workspace_binding=binding,
                runtime_principal_snapshot=principal_snapshot,
                status="completed",
            )
        )

    async with ArtifactsUnitOfWork(engine) as uow:
        session = await uow.session.get(NetworkSessionModel, session_id)
        execution = await uow.session.get(NetworkExecutionModel, execution_id)
        assert session.artifact_workspace_binding == binding
        assert execution.artifact_workspace_binding == binding
        assert execution.runtime_principal_snapshot == principal_snapshot
        assert execution.input_content_parts == [
            {
                "type": "artifact",
                "ref": {
                    "artifact_id": "report-1",
                    "revision_id": "report-revision-3",
                },
                "media_type_hint": "application/pdf",
            }
        ]
        snapshot = NetworkRuntimeLoader._execution_snapshot(execution)
        assert snapshot.artifact_workspace_binding == binding
        assert snapshot.runtime_principal_snapshot == principal_snapshot
        assert snapshot.input_content_parts == tuple(execution.input_content_parts)


@pytest.mark.asyncio
async def test_two_users_keep_three_logical_workspace_journeys_isolated(
    artifacts_database, engine, monkeypatch
):
    from modules.artifacts.composition import runtime_binding

    monkeypatch.setattr(runtime_binding, "DATABASE_ENGINE", engine)
    monkeypatch.setattr(
        runtime_binding, "ExistingPrincipalAuthority", lambda _uow: _TestAuthority()
    )

    project_id = UUID(artifacts_database["project_id"])
    scope = Scope(str(project_id), Environment.STAGING)
    user_a, user_b = uuid4(), uuid4()
    principals = {
        user_id: AuthenticatedPrincipal(
            user_id=user_id,
            session_id=uuid4(),
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        for user_id in (user_a, user_b)
    }
    journeys = (
        ("journey-user-a-exam", "tutor-user-a", "exam", user_a),
        ("journey-user-a-math", "tutor-user-a", "math", user_a),
        ("journey-user-b-exam", "tutor-user-b", "exam", user_b),
    )
    async with ArtifactsUnitOfWork(engine) as uow:
        from modules.artifacts.infra.database.catalog import CatalogRepository

        catalog = CatalogRepository(uow)
        for workspace_id, namespace, external_key, user_id in journeys:
            await catalog.insert_workspace(Workspace(
                id=workspace_id,
                scope=scope,
                external_namespace=namespace,
                external_key=external_key,
                name=workspace_id,
                catalog_version=1,
            ))
            uow.session.add(GrantModel(
                id=str(uuid4()),
                project_id=project_id,
                environment=scope.environment.value,
                principal_id=f"user-{user_id}",
                workspace_id=workspace_id,
                external_namespace=None,
                actions=[Action.READ.value, Action.SEARCH.value],
                revision=1,
                revoked=False,
            ))

    resolved = {}
    for workspace_id, namespace, external_key, user_id in journeys:
        binding = await runtime_binding.resolve_runtime_artifact_workspace_binding(
            principal=principals[user_id],
            project_id=project_id,
            environment="staging",
            external_namespace=namespace,
            external_key=external_key,
            actions=("read", "search"),
            binding_scope="session",
        )
        assert binding.workspace_id == workspace_id
        resolved[(user_id, external_key)] = binding.workspace_id

    assert resolved[(user_a, "exam")] != resolved[(user_a, "math")]
    assert resolved[(user_a, "exam")] != resolved[(user_b, "exam")]

    async with ArtifactsUnitOfWork(engine) as uow:
        authorization = ArtifactAuthorization(_TestAuthority(), GrantRepository(uow))
        for user_id, workspace_id in (
            (user_a, "journey-user-a-exam"),
            (user_a, "journey-user-a-math"),
            (user_b, "journey-user-b-exam"),
        ):
            workspace = await authorization.authorize(
                principals[user_id], scope, workspace_id, Action.READ,
            )
            assert workspace.id == workspace_id
        for user_id, workspace_id in (
            (user_a, "journey-user-b-exam"),
            (user_b, "journey-user-a-exam"),
            (user_b, "journey-user-a-math"),
        ):
            with pytest.raises(ArtifactError) as denied:
                await authorization.authorize(
                    principals[user_id], scope, workspace_id, Action.READ,
                )
            assert denied.value.code == "ARTIFACT_ACCESS_DENIED"
