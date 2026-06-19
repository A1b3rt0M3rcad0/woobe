from sqlalchemy import Index

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    DocumentModel,
)

AGENT_PROJECT_STATUS_INDEX = Index(
    "ix_agent_agents_project_status",
    AgentModel.project_id,
    AgentModel.status,
)

RELEASE_PROJECT_AGENT_CREATED_INDEX = Index(
    "ix_agent_releases_project_agent_created",
    AgentReleaseModel.project_id,
    AgentReleaseModel.agent_id,
    AgentReleaseModel.created_at.desc(),
)

DOCUMENT_PROJECT_STATUS_INDEX = Index(
    "ix_agent_documents_project_status_indexed",
    DocumentModel.project_id,
    DocumentModel.status,
    DocumentModel.indexed_at,
)
