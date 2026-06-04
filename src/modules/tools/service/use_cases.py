from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.events import OutboxEventWriter
from shared.infra.crypto import encrypt_secret
from modules.tools.infra.models import OutboxEventModel
from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import ToolStatus
from modules.tools.domain.errors import ToolNotFoundError
from modules.tools.domain.repositories import SecretRepository, ToolRepository
from modules.tools.service.dtos import (
    CreateSecretInput,
    CreateSecretOutput,
    CreateToolInput,
    CreateToolOutput,
    ListSecretsInput,
    ListToolsByAgentInput,
    ListToolsInput,
)


class CreateToolUseCase:

    def __init__(
        self,
        repo: ToolRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self.repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateToolInput) -> CreateToolOutput:
        tool = Tool(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            name=input_dto.name,
            description=input_dto.description,
            type=input_dto.type,
            config=input_dto.config,
            input_schema=input_dto.input_schema,
            output_schema=input_dto.output_schema,
            risk_level=input_dto.risk_level,
            timeout_ms=input_dto.timeout_ms,
        )
        created = await self.repo.create(tool)

        await self._outbox.write(
            aggregate_type="tool",
            aggregate_id=created.id,
            event_type="tools.tool.created",
            payload={
                "tool_id": str(created.id),
                "project_id": str(created.project_id),
                "agent_id": str(created.agent_id),
                "name": created.name,
                "type": created.type,
                "risk_level": created.risk_level,
            },
        )

        return CreateToolOutput(
            id=created.id,
            project_id=created.project_id,
            agent_id=created.agent_id,
            name=created.name,
            description=created.description,
            type=created.type,
            config=created.config,
            input_schema=created.input_schema,
            output_schema=created.output_schema,
            risk_level=created.risk_level,
            timeout_ms=created.timeout_ms,
            status=created.status,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


class CreateSecretUseCase:

    def __init__(
        self,
        repo: SecretRepository,
        outbox: OutboxEventWriter,
        encryption_key: str | None = None,
    ) -> None:
        self.repo = repo
        self._outbox = outbox
        self.encryption_key = encryption_key or os.getenv("SECRETS_ENCRYPTION_KEY", "default-dev-key")

    async def execute(self, input_dto: CreateSecretInput) -> CreateSecretOutput:
        encrypted = encrypt_secret(input_dto.value, self.encryption_key)

        secret = Secret(
            project_id=input_dto.project_id,
            name=input_dto.name,
            type=input_dto.type,
            encrypted_value=encrypted,
            data=input_dto.data,
        )
        created = await self.repo.create(secret)

        await self._outbox.write(
            aggregate_type="secret",
            aggregate_id=created.id,
            event_type="tools.secret.created",
            payload={
                "secret_id": str(created.id),
                "project_id": str(created.project_id),
                "name": created.name,
                "type": created.type,
            },
        )

        return CreateSecretOutput(
            id=created.id,
            project_id=created.project_id,
            name=created.name,
            type=created.type,
            data=created.data,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


class ExecuteToolUseCase:

    def __init__(
        self,
        session: AsyncSession,
        tool_repo: ToolRepository,
    ) -> None:
        self.session = session
        self.tool_repo = tool_repo

    async def execute(self, tool_id, input_data: dict | None = None) -> dict:
        tool = await self.tool_repo.get_by_id(tool_id)

        if tool.status != ToolStatus.ACTIVE:
            raise ToolNotFoundError(tool_id)

        event = OutboxEventModel(
            aggregate_type="tool",
            aggregate_id=tool.id,
            event_type="tools.tool.executed",
            payload={
                "tool_id": str(tool.id),
                "input": input_data,
            },
        )
        self.session.add(event)

        return {"executed": True, "tool_id": str(tool.id), "name": tool.name}


class ListToolsUseCase:

    def __init__(self, repo: ToolRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListToolsInput) -> list:
        if not input_dto.project_id:
            return []
        return await self._repo.list_by_project(input_dto.project_id)


class ListToolsByAgentUseCase:

    def __init__(self, repo: ToolRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListToolsByAgentInput) -> list:
        return await self._repo.list_by_agent(input_dto.agent_id)


class ListSecretsUseCase:

    def __init__(self, repo: SecretRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListSecretsInput) -> list:
        if not input_dto.project_id:
            return []
        return await self._repo.list_by_project(input_dto.project_id)

