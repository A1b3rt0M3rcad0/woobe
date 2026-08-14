from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from modules.agent.infra.database.models import AgentModel, DocumentCollectionModel
from modules.core.infra.database.models import ProjectMemberModel, ProjectModel
from modules.identity.infra.database.models import (
    WorkspaceMemberModel,
    WorkspaceModel,
    UserModel,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import ConflictError, NotFoundError
from shared.security.tenancy import TenantAuthorizer


@pytest.fixture
async def project_access_graph():
    engine = create_engine(Settings.model_validate({}))
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)

    owner_id = uuid4()
    member_id = uuid4()
    workspace_id = uuid4()
    project_a_id = uuid4()
    project_b_id = uuid4()
    agent_a_id = uuid4()
    collection_b_id = uuid4()

    async with session_factory() as session:
        transaction = await session.begin()
        session.add_all(
            [
                UserModel(id=owner_id, email=f"project-owner-{owner_id}@example.test", password=b"password-hash-owner", status="active"),
                UserModel(id=member_id, email=f"project-member-{member_id}@example.test", password=b"password-hash-member", status="active"),
                WorkspaceModel(id=workspace_id, name="Project Access Workspace", slug=f"project-access-{workspace_id}", status="active"),
            ]
        )
        await session.flush()

        session.add_all(
            [
                WorkspaceMemberModel(id=uuid4(), user_id=owner_id, workspace_id=workspace_id, role="owner", status="active", joined_at=now),
                WorkspaceMemberModel(id=uuid4(), user_id=member_id, workspace_id=workspace_id, role="member", status="active", joined_at=now),
                ProjectModel(id=project_a_id, workspace_id=workspace_id, name="Allowed Project", slug=f"allowed-{project_a_id}", status="active", data={}),
                ProjectModel(id=project_b_id, workspace_id=workspace_id, name="Restricted Project", slug=f"restricted-{project_b_id}", status="active", data={}),
            ]
        )
        await session.flush()

        session.add_all(
            [
                ProjectMemberModel(id=uuid4(), project_id=project_a_id, user_id=member_id, status="active"),
                AgentModel(
                    id=agent_a_id,
                    project_id=project_a_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="Project A Agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="gpt-test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=None,
                    max_output_tokens=None,
                    session_mode="stateful",
                    status="active",
                    settings={},
                ),
                DocumentCollectionModel(id=collection_b_id, project_id=project_b_id, name="Project B Collection", description=None, status="active"),
            ]
        )
        await session.flush()

        yield {
            "session": session,
            "owner_id": owner_id,
            "member_id": member_id,
            "project_a_id": project_a_id,
            "project_b_id": project_b_id,
            "agent_a_id": agent_a_id,
            "collection_b_id": collection_b_id,
        }

        await transaction.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_member_can_access_only_explicit_projects(project_access_graph):
    graph = project_access_graph
    authorizer = TenantAuthorizer(graph["session"])
    await authorizer.authorize(user_id=graph["member_id"], path_params={"project_id": graph["project_a_id"]}, query_params={}, body=None)
    with pytest.raises(NotFoundError):
        await authorizer.authorize(user_id=graph["member_id"], path_params={"project_id": graph["project_b_id"]}, query_params={}, body=None)


@pytest.mark.asyncio
async def test_workspace_owner_has_implicit_project_access(project_access_graph):
    graph = project_access_graph
    await TenantAuthorizer(graph["session"]).authorize(user_id=graph["owner_id"], path_params={"project_id": graph["project_b_id"]}, query_params={}, body=None)


@pytest.mark.asyncio
async def test_cross_project_relationship_is_rejected(project_access_graph):
    graph = project_access_graph
    with pytest.raises(ConflictError):
        await TenantAuthorizer(graph["session"]).authorize(
            user_id=graph["member_id"],
            path_params={"agent_id": graph["agent_a_id"]},
            query_params={},
            body={"collection_id": graph["collection_b_id"]},
        )
