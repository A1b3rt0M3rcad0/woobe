from uuid import UUID

from pydantic import BaseModel


class CreateAgentChatSurfaceSessionInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    agent_release_id: UUID
    release_version: str
    chat_surface_id: UUID


class CloseAgentChatSurfaceSessionInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    agent_release_id: UUID
    chat_surface_id: UUID
    session_id: UUID


class AgentChatSurfaceSessionState(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    agent_release_id: UUID
    chat_surface_id: UUID
    status: str
