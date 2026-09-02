from uuid import UUID

from pydantic import BaseModel


class CreateNetworkChatSurfaceSessionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_version_id: UUID
    chat_surface_id: UUID


class CloseNetworkChatSurfaceSessionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    network_version_id: UUID
    chat_surface_id: UUID
    session_id: UUID


class NetworkChatSurfaceSessionState(BaseModel):
    id: UUID
    project_id: UUID
    network_id: UUID
    network_version_id: UUID
    chat_surface_id: UUID
    status: str
