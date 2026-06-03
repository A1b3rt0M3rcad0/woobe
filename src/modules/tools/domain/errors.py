from __future__ import annotations

from uuid import UUID

from shared.domain.errors import ConflictError, NotFoundError


class ToolNotFoundError(NotFoundError):
    def __init__(self, tool_id: UUID) -> None:
        self.tool_id = tool_id
        super().__init__(f"Tool not found: {tool_id}")


class SecretNotFoundError(NotFoundError):
    def __init__(self, secret_id: UUID) -> None:
        self.secret_id = secret_id
        super().__init__(f"Secret not found: {secret_id}")


class DuplicateSecretError(ConflictError):
    def __init__(self, name: str, project_id: UUID) -> None:
        self.name = name
        self.project_id = project_id
        super().__init__(f"Secret '{name}' already exists in project {project_id}")
