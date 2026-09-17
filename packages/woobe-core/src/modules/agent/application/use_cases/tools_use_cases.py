from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.outbox import OutboxEventWriter

from modules.agent.application.dtos.tools_dtos import (
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
    ToolUsageImpactOutput,
    UpdateToolInput,
    UpdateToolStatusInput,
)
from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.application.interfaces.ports import (
    SecretCipherPort,
    ToolExecutionPort,
    ToolSecretResolverPort,
)
from modules.agent.application.tool_context_bindings import merge_context_bindings_for_update
from modules.agent.domain.entities import Secret, Tool
from modules.agent.domain.enums import ReleaseStatus, ToolStatus
from modules.agent.domain.errors import ToolInUseError, ToolNotFoundError
from modules.agent.domain.events import (
    AgentSecretCreatedV1,
    AgentToolCreatedV1,
    AgentToolStatusChangedV1,
    AgentToolUpdatedV1,
)
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    AgentRepository,
    SecretRepository,
    ToolRepository,
)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _release_references_tool(release, tool_id: UUID) -> bool:
    runtime_config = getattr(release, "runtime_config", None)
    if not isinstance(runtime_config, dict):
        return False
    tools_config = runtime_config.get("tools")
    if not isinstance(tools_config, dict):
        return False

    target = str(tool_id)
    raw_tool_ids = tools_config.get("tool_ids")
    if isinstance(raw_tool_ids, list):
        for raw_tool_id in raw_tool_ids:
            if str(raw_tool_id) == target:
                return True

    raw_snapshots = tools_config.get("snapshots")
    if isinstance(raw_snapshots, list):
        for snapshot in raw_snapshots:
            if isinstance(snapshot, dict) and str(snapshot.get("id")) == target:
                return True

    return False


class CreateToolUseCase:

    def __init__(
        self,
        repo: ToolRepository,
        outbox: OutboxEventWriter,
        mcp_bootstrapper: McpToolBootstrapper | None = None,
    ) -> None:
        self.repo = repo
        self._outbox = outbox
        self._mcp_bootstrapper = mcp_bootstrapper

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

        if self._mcp_bootstrapper is not None:
            bootstrapped = await self._mcp_bootstrapper.bootstrap(created)
            if bootstrapped is not None:
                created = await self.repo.update(created)

        event = AgentToolCreatedV1.create(
            tool_id=created.id,
            project_id=created.project_id,
            agent_id=created.agent_id,
            payload={
                "name": created.name,
                "type": created.type.value if hasattr(created.type, "value") else created.type,
                "risk_level": created.risk_level.value if hasattr(created.risk_level, "value") else created.risk_level,
                "mcp_status": (created.config or {}).get("mcp_status") if created.config else None,
            },
        )
        await self._outbox.write(event)

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
        cipher: SecretCipherPort,
    ) -> None:
        self.repo = repo
        self._outbox = outbox
        self._cipher = cipher

    async def execute(self, input_dto: CreateSecretInput) -> CreateSecretOutput:
        encrypted = await self._cipher.encrypt(input_dto.value)

        secret = Secret(
            project_id=input_dto.project_id,
            name=input_dto.name,
            type=input_dto.type,
            encrypted_value=encrypted,
            data=input_dto.data,
        )
        created = await self.repo.create(secret)

        event = AgentSecretCreatedV1.create(
            secret_id=created.id,
            project_id=created.project_id,
            name=created.name,
            secret_type=created.type.value if hasattr(created.type, "value") else created.type,
        )
        await self._outbox.write(event)

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
            tool.config = merge_context_bindings_for_update(
                tool.config,
                input_dto.config,
            )
        if input_dto.input_schema is not None:
            tool.input_schema = input_dto.input_schema
        if input_dto.output_schema is not None:
            tool.output_schema = input_dto.output_schema
        if input_dto.risk_level is not None:
            tool.risk_level = input_dto.risk_level
        if input_dto.timeout_ms is not None:
            tool.timeout_ms = input_dto.timeout_ms

        updated = await self._repo.update(tool)

        event = AgentToolUpdatedV1.create(
            tool_id=updated.id,
            payload={"name": updated.name},
        )
        await self._outbox.write(event)

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

        status_value = updated.status.value if hasattr(updated.status, "value") else updated.status
        event = AgentToolStatusChangedV1.create(
            tool_id=updated.id,
            status=status_value,
        )
        await self._outbox.write(event)

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


class GetToolUsageImpactUseCase:

    def __init__(
        self,
        tool_repo: ToolRepository,
        agent_repo: AgentRepository,
        release_repo: AgentReleaseRepository,
    ) -> None:
        self._tool_repo = tool_repo
        self._agent_repo = agent_repo
        self._release_repo = release_repo

    async def execute(self, tool_id: UUID) -> ToolUsageImpactOutput:
        tool = await self._tool_repo.get_by_id(tool_id)
        agents = await self._agent_repo.list_by_project(tool.project_id)

        draft_agents: set[UUID] = set()
        staging_agents: set[UUID] = set()
        production_agents: set[UUID] = set()
        historical_releases = 0
        total_references = 0

        for agent in agents:
            releases = await self._release_repo.list_by_agent(agent.id)
            for release in releases:
                if not _release_references_tool(release, tool_id):
                    continue

                total_references += 1
                status = _value(release.status)
                if status == ReleaseStatus.draft.value:
                    draft_agents.add(agent.id)
                elif status == ReleaseStatus.staging.value:
                    staging_agents.add(agent.id)
                elif status == ReleaseStatus.production.value:
                    production_agents.add(agent.id)
                else:
                    historical_releases += 1

        in_use = total_references > 0
        return ToolUsageImpactOutput(
            tool_id=tool.id,
            status=tool.status,
            in_use=in_use,
            can_delete=not in_use,
            can_retire=_value(tool.status) != ToolStatus.DEPRECATED.value,
            draft_agents=len(draft_agents),
            staging_agents=len(staging_agents),
            production_agents=len(production_agents),
            historical_releases=historical_releases,
            total_references=total_references,
        )


class DeleteToolUseCase:

    def __init__(
        self,
        repo: ToolRepository,
        agent_repo: AgentRepository,
        release_repo: AgentReleaseRepository,
    ) -> None:
        self._repo = repo
        self._usage = GetToolUsageImpactUseCase(repo, agent_repo, release_repo)

    async def execute(self, input_dto: DeleteToolInput) -> None:
        impact = await self._usage.execute(input_dto.tool_id)
        if impact.in_use:
            raise ToolInUseError(input_dto.tool_id, impact)
        await self._repo.delete(input_dto.tool_id)


class ExecuteToolUseCase:

    def __init__(
        self,
        tool_repo: ToolRepository,
        tool_executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._tool_executor = tool_executor
        self._secret_resolver = secret_resolver

    async def execute(self, input_dto: ExecuteToolInput) -> ExecuteToolOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)

        if tool.status != ToolStatus.ACTIVE:
            raise ToolNotFoundError(input_dto.tool_id)

        config = tool.config or {}
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        body = config.get("body")

        raw_headers = config.get("headers", []) or []
        if self._secret_resolver:
            headers = await self._secret_resolver.resolve_headers(raw_headers, tool.project_id)
        else:
            headers = {h.get("key", ""): h.get("value", "") for h in raw_headers if h.get("key")}

        variables = config.get("variables", {}) or {}
        merged_input = {**variables, **(input_dto.input_data or {})}
        url = self._resolve_url(url, merged_input)
        if body:
            body = self._resolve_template(body, merged_input)

        result = await self._tool_executor.execute(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout_ms=tool.timeout_ms or 30000,
        )

        return ExecuteToolOutput(
            success=result.success,
            output=result.output,
            duration_ms=result.duration_ms,
            error=result.error,
        )

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

    def __init__(self, tool_executor: ToolExecutionPort) -> None:
        self._tool_executor = tool_executor

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

        result = await self._tool_executor.execute(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout_ms=30000,
        )

        return TestToolOutput(
            success=result.success,
            status_code=result.status_code,
            headers=result.headers,
            body=result.body,
            duration_ms=result.duration_ms,
            error=result.error,
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