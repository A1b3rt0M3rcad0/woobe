from __future__ import annotations

import json
import os
import time
from uuid import UUID

import httpx

from shared.domain.events import OutboxEventWriter
from shared.infra.crypto import encrypt_secret
from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import ToolStatus
from modules.tools.domain.errors import ToolNotFoundError
from modules.tools.domain.repositories import SecretRepository, ToolRepository
from modules.tools.application.dtos.tools_dtos import (
    CreateSecretInput,
    CreateSecretOutput,
    CreateToolInput,
    CreateToolOutput,
    DeleteToolInput,
    ExecuteToolInput,
    ExecuteToolOutput,
    ListSecretsInput,
    ListToolsByAgentInput,
    ListToolsInput,
    TestToolInput,
    TestToolOutput,
    UpdateToolInput,
    UpdateToolStatusInput,
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
                "agent_id": str(created.agent_id) if created.agent_id else None,
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


class UpdateToolUseCase:

    def __init__(
        self,
        repo: ToolRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, tool_id: UUID, input_dto: UpdateToolInput) -> CreateToolOutput:
        tool = await self._repo.get_by_id(tool_id)

        if input_dto.name is not None:
            tool.name = input_dto.name
        if input_dto.description is not None:
            tool.description = input_dto.description
        if "agent_id" in input_dto.model_fields_set:
            tool.agent_id = input_dto.agent_id
        if input_dto.config is not None:
            tool.config = input_dto.config
        if input_dto.input_schema is not None:
            tool.input_schema = input_dto.input_schema
        if input_dto.output_schema is not None:
            tool.output_schema = input_dto.output_schema
        if input_dto.risk_level is not None:
            tool.risk_level = input_dto.risk_level
        if input_dto.timeout_ms is not None:
            tool.timeout_ms = input_dto.timeout_ms

        updated = await self._repo.update(tool)

        await self._outbox.write(
            aggregate_type="tool",
            aggregate_id=updated.id,
            event_type="tools.tool.updated",
            payload={
                "tool_id": str(updated.id),
                "name": updated.name,
            },
        )

        return CreateToolOutput(
            id=updated.id,
            project_id=updated.project_id,
            agent_id=updated.agent_id,
            name=updated.name,
            description=updated.description,
            type=updated.type,
            config=updated.config,
            input_schema=updated.input_schema,
            output_schema=updated.output_schema,
            risk_level=updated.risk_level,
            timeout_ms=updated.timeout_ms,
            status=updated.status,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )


class UpdateToolStatusUseCase:

    def __init__(self, repo: ToolRepository, outbox: OutboxEventWriter) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, tool_id: UUID, input_dto: UpdateToolStatusInput) -> CreateToolOutput:
        tool = await self._repo.get_by_id(tool_id)
        tool.status = input_dto.status
        updated = await self._repo.update(tool)

        await self._outbox.write(
            aggregate_type="tool",
            aggregate_id=updated.id,
            event_type="tools.tool.status_changed",
            payload={
                "tool_id": str(updated.id),
                "status": updated.status.value if hasattr(updated.status, "value") else updated.status,
            },
        )

        return CreateToolOutput(
            id=updated.id,
            project_id=updated.project_id,
            agent_id=updated.agent_id,
            name=updated.name,
            description=updated.description,
            type=updated.type,
            config=updated.config,
            input_schema=updated.input_schema,
            output_schema=updated.output_schema,
            risk_level=updated.risk_level,
            timeout_ms=updated.timeout_ms,
            status=updated.status,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )


class DeleteToolUseCase:

    def __init__(self, repo: ToolRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: DeleteToolInput) -> None:
        await self._repo.delete(input_dto.tool_id)


class ExecuteToolUseCase:

    def __init__(
        self,
        tool_repo: ToolRepository,
        secret_repo: SecretRepository | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._secret_repo = secret_repo
        self._encryption_key = encryption_key or os.getenv("SECRETS_ENCRYPTION_KEY", "default-dev-key")

    async def execute(self, input_dto: ExecuteToolInput) -> ExecuteToolOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)

        if tool.status != ToolStatus.ACTIVE:
            raise ToolNotFoundError(input_dto.tool_id)

        config = tool.config or {}
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = self._resolve_headers(config.get("headers", []))
        body = config.get("body")

        variables = config.get("variables", {}) or {}
        merged_input = {**variables, **(input_dto.input_data or {})}
        url = self._resolve_url(url, merged_input)
        if body:
            body = self._resolve_template(body, merged_input)

        started_at = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(tool.timeout_ms / 1000 if tool.timeout_ms else 30.0)) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body.encode() if body else None,
                )
                duration_ms = round((time.monotonic() - started_at) * 1000)

                response_body = response.text
                try:
                    output = json.loads(response_body)
                except (json.JSONDecodeError, ValueError):
                    output = {"raw": response_body}

                return ExecuteToolOutput(
                    success=response.is_success,
                    output={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": output,
                    },
                    duration_ms=duration_ms,
                    error=None if response.is_success else f"HTTP {response.status_code}: {response_body[:500]}",
                )

        except httpx.TimeoutException as e:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return ExecuteToolOutput(
                success=False,
                output=None,
                duration_ms=duration_ms,
                error=f"Request timed out after {tool.timeout_ms or 30000}ms: {e}",
            )
        except httpx.RequestError as e:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return ExecuteToolOutput(
                success=False,
                output=None,
                duration_ms=duration_ms,
                error=f"Request failed: {e}",
            )

    def _resolve_headers(self, headers: list[dict]) -> dict[str, str]:
        resolved = {}
        for h in headers:
            key = h.get("key", "")
            value = h.get("value", "")
            if value.startswith("{{secret:") and self._secret_repo:
                try:
                    from shared.infra.crypto import decrypt_secret
                    secret = self._secret_repo.get_by_name()
                    if secret:
                        value = decrypt_secret(secret.encrypted_value, self._encryption_key)
                except Exception:
                    value = ""
            resolved[key] = value
        return resolved

    def _resolve_url(self, url: str, variables: dict) -> str:
        import re
        def replace_var(match):
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))
        return re.sub(r'\{\{(\w+)\}\}', replace_var, url)

    def _resolve_template(self, template: str, variables: dict) -> str:
        import re
        def replace_var(match):
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))
        return re.sub(r'\{\{(\w+)\}\}', replace_var, template)


class TestToolUseCase:

    def __init__(self) -> None:
        pass

    async def execute(self, input_dto: TestToolInput) -> TestToolOutput:
        config = input_dto.config or {}
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        raw_headers = config.get("headers", []) or []
        headers = {h.get("key", ""): h.get("value", "") for h in raw_headers if h.get("key")}
        body = config.get("body")

        variables = config.get("variables", {}) or {}
        merged = {**variables, **(input_dto.input_data or {})}

        import re
        def replace_var(match):
            var_name = match.group(1)
            return str(merged.get(var_name, match.group(0)))
        url = re.sub(r'\{\{(\w+)\}\}', replace_var, url)
        if body:
            body = re.sub(r'\{\{(\w+)\}\}', replace_var, body)

        started_at = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body.encode() if body else None,
                )
                duration_ms = round((time.monotonic() - started_at) * 1000)
                return TestToolOutput(
                    success=response.is_success,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text,
                    duration_ms=duration_ms,
                    error=None if response.is_success else f"HTTP {response.status_code}",
                )
        except httpx.TimeoutException as e:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return TestToolOutput(
                success=False, duration_ms=duration_ms, error=f"Timeout: {e}",
            )
        except httpx.RequestError as e:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return TestToolOutput(
                success=False, duration_ms=duration_ms, error=f"Request failed: {e}",
            )


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
