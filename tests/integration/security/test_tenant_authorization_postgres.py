from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from modules.agent.infra.database.models import (
    AgentCollectionModel,
    AgentModel,
    AgentPromptModel,
    AgentToolModel,
    DocumentCollectionModel,
    DocumentModel,
    MessageModel,
    ProviderCredentialModel,
    SessionModel,
)
from modules.core.infra.database.models import ApiKeyModel, ProjectModel
from modules.identity.infra.database.models import (
    WorkspaceMemberModel,
    WorkspaceModel,
    UserModel,
)
from modules.observability.infra.database.models import TraceModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import NotFoundError
from shared.security.tenancy import TenantAuthorizer


@pytest.fixture
async def tenant_graph():
    engine = create_engine(Settings.model_validate({}))
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)

    user_a_id, user_b_id = uuid4(), uuid4()
    workspace_a_id, workspace_b_id = uuid4(), uuid4()
    project_a_id, project_b_id = uuid4(), uuid4()
    credential_id = uuid4()
    agent_id = uuid4()
    prompt_id = uuid4()
    collection_id = uuid4()
    collection_link_id = uuid4()
    document_id = uuid4()
    tool_id = uuid4()
    session_id = uuid4()
    message_id = uuid4()
    trace_id = uuid4()
    api_key_id = uuid4()

    async with session_factory() as session:
        transaction = await session.begin()

        session.add_all(
            [
                UserModel(
                    id=user_a_id,
                    email=f"tenant-a-{user_a_id}@example.test",
                    password=b"password-hash-a",
                    status="active",
                ),
                UserModel(
                    id=user_b_id,
                    email=f"tenant-b-{user_b_id}@example.test",
                    password=b"password-hash-b",
                    status="active",
                ),
                WorkspaceModel(
                    id=workspace_a_id,
                    name="Tenant A",
                    slug=f"tenant-a-{workspace_a_id}",
                    status="active",
                ),
                WorkspaceModel(
                    id=workspace_b_id,
                    name="Tenant B",
                    slug=f"tenant-b-{workspace_b_id}",
                    status="active",
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                WorkspaceMemberModel(
                    id=uuid4(),
                    user_id=user_a_id,
                    workspace_id=workspace_a_id,
                    role="owner",
                    status="active",
                    joined_at=now,
                ),
                WorkspaceMemberModel(
                    id=uuid4(),
                    user_id=user_b_id,
                    workspace_id=workspace_b_id,
                    role="owner",
                    status="active",
                    joined_at=now,
                ),
                ProjectModel(
                    id=project_a_id,
                    workspace_id=workspace_a_id,
                    name="Project A",
                    slug=f"project-a-{project_a_id}",
                    status="active",
                    data={},
                ),
                ProjectModel(
                    id=project_b_id,
                    workspace_id=workspace_b_id,
                    name="Project B",
                    slug=f"project-b-{project_b_id}",
                    status="active",
                    data={},
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                ApiKeyModel(
                    id=api_key_id,
                    project_id=project_b_id,
                    credential_id=api_key_id,
                    name="Tenant B key",
                    key_prefix=f"tb{api_key_id.hex[:10]}",
                    key_hash=api_key_id.bytes + project_b_id.bytes,
                    key_version=1,
                    scopes=["runtime:execute"],
                    status="active",
                    created_by_user_id=user_b_id,
                ),
                ProviderCredentialModel(
                    id=credential_id,
                    project_id=project_b_id,
                    provider="openai",
                    name="Tenant B OpenAI",
                    encrypted_secret="encrypted-test-value",
                    status="active",
                    meta={},
                ),
                DocumentCollectionModel(
                    id=collection_id,
                    project_id=project_b_id,
                    name="Tenant B knowledge",
                    description=None,
                    status="active",
                ),
            ]
        )
        await session.flush()

        session.add(
            AgentModel(
                id=agent_id,
                project_id=project_b_id,
                provider_credential_id=credential_id,
                fallback_credential_id=None,
                name="Tenant B agent",
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
            )
        )
        await session.flush()

        session.add_all(
            [
                AgentPromptModel(
                    id=prompt_id,
                    project_id=project_b_id,
                    agent_id=agent_id,
                    version="v1",
                    name="Prompt v1",
                    content="Be precise.",
                    content_hash=None,
                    status="draft",
                    created_by=user_b_id,
                ),
                AgentCollectionModel(
                    id=collection_link_id,
                    agent_id=agent_id,
                    collection_id=collection_id,
                ),
                DocumentModel(
                    id=document_id,
                    project_id=project_b_id,
                    collection_id=collection_id,
                    title="Tenant B document",
                    file_name="tenant-b.txt",
                    content_type="text/plain",
                    size_bytes=4,
                    storage_key=f"tests/{document_id}",
                    parser="text",
                    status="uploaded",
                    error=None,
                    page_count=1,
                    chunk_count=0,
                    sha256=None,
                    indexed_at=None,
                ),
                AgentToolModel(
                    id=tool_id,
                    project_id=project_b_id,
                    agent_id=agent_id,
                    name="tenant_b_tool",
                    description=None,
                    type="http",
                    config={},
                    input_schema={},
                    output_schema={},
                    risk_level="low",
                    timeout_ms=1000,
                    status="active",
                ),
                SessionModel(
                    id=session_id,
                    project_id=project_b_id,
                    agent_id=agent_id,
                    external_session_id=f"ext-{session_id}",
                    tenant_id="tenant-b",
                    user_id=str(user_b_id),
                    status="active",
                    mode="chat",
                    data={},
                    last_message_at=now,
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                MessageModel(
                    id=message_id,
                    project_id=project_b_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    role="assistant",
                    content="Tenant B only",
                    input_tokens=None,
                    output_tokens=None,
                    cost_usd=None,
                    data={},
                ),
                TraceModel(
                    id=trace_id,
                    project_id=project_b_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    external_session_id=None,
                    tenant_id="tenant-b",
                    user_id=str(user_b_id),
                    status="pending",
                    started_at=now,
                    ended_at=None,
                    total_latency_ms=None,
                    total_cost_usd=None,
                    provider="openai",
                    model="gpt-test",
                    fallback_used=False,
                    error=None,
                    data={},
                ),
            ]
        )
        await session.flush()

        yield session, {
            "owner_user_id": user_b_id,
            "foreign_user_id": user_a_id,
            "workspace_id": workspace_b_id,
            "project_id": project_b_id,
            "api_key_id": api_key_id,
            "credential_id": credential_id,
            "agent_id": agent_id,
            "version_id": prompt_id,
            "collection_id": collection_id,
            "link_id": collection_link_id,
            "document_id": document_id,
            "tool_id": tool_id,
            "session_id": session_id,
            "message_id": message_id,
            "trace_id": trace_id,
        }

        if transaction.is_active:
            await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_tenant_matrix_hides_every_private_resource_from_foreign_user(
    tenant_graph,
) -> None:
    session, graph = tenant_graph
    authorizer = TenantAuthorizer(session)

    resource_matrix: list[tuple[str, UUID]] = [
        ("workspace_id", graph["workspace_id"]),
        ("project_id", graph["project_id"]),
        ("api_key_id", graph["api_key_id"]),
        ("credential_id", graph["credential_id"]),
        ("agent_id", graph["agent_id"]),
        ("version_id", graph["version_id"]),
        ("collection_id", graph["collection_id"]),
        ("link_id", graph["link_id"]),
        ("document_id", graph["document_id"]),
        ("tool_id", graph["tool_id"]),
        ("session_id", graph["session_id"]),
        ("message_id", graph["message_id"]),
        ("trace_id", graph["trace_id"]),
    ]

    for key, resource_id in resource_matrix:
        await authorizer.authorize(
            user_id=graph["owner_user_id"],
            path_params={key: str(resource_id)},
            query_params={},
            body=None,
        )

        with pytest.raises(NotFoundError, match="Resource not found"):
            await authorizer.authorize(
                user_id=graph["foreign_user_id"],
                path_params={key: str(resource_id)},
                query_params={},
                body=None,
            )


@pytest.mark.asyncio
async def test_api_key_project_matrix_rejects_nested_foreign_resource_identifiers(
    tenant_graph,
) -> None:
    session, graph = tenant_graph
    authorizer = TenantAuthorizer(session)

    await authorizer.authorize_api_key(
        project_id=graph["project_id"],
        path_params={"session_id": str(graph["session_id"])},
        query_params={},
        body={
            "project_id": str(graph["project_id"]),
            "agent": {"agent_id": str(graph["agent_id"])},
        },
    )

    with pytest.raises(NotFoundError, match="Resource not found"):
        await authorizer.authorize_api_key(
            project_id=uuid4(),
            path_params={"session_id": str(graph["session_id"])},
            query_params={},
            body={"agent_id": str(graph["agent_id"])},
        )
