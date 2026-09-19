from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.tools_dtos import (
    ExecuteToolInput,
    ExecuteToolOutput,
    TestToolInput,
    TestToolOutput,
)
from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.application.interfaces.tool_runtime import ToolRuntimeRegistry
from modules.agent.application.tool_context_bindings import (
    ToolContextBindingError,
    apply_context_bindings,
    collect_project_environment_binding_keys,
)
from modules.agent.application.tool_templates import (
    ToolTemplateResolutionError,
    collect_project_environment_keys,
    resolve_tool_templates,
)
from modules.agent.domain.enums import ToolStatus
from modules.agent.domain.errors import ToolNotFoundError


class RuntimeExecuteToolUseCase:
    def __init__(
        self,
        tool_repo: ToolRepository,
        runtime_registry: ToolRuntimeRegistry | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._runtime_registry = runtime_registry

    async def execute(self, input_dto: ExecuteToolInput) -> ExecuteToolOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool.status != ToolStatus.ACTIVE:
            raise ToolNotFoundError(input_dto.tool_id)

        if self._runtime_registry is None:
            return ExecuteToolOutput(
                success=False,
                error="Tool runtime is not configured",
            )

        result = await self._runtime_registry.execute(
            tool,
            input_dto.input_data or {},
        )
        return ExecuteToolOutput(
            success=result.success,
            output=result.output,
            duration_ms=result.duration_ms,
            error=result.error,
        )


ProjectEnvironmentResolver = Callable[
    ...,
    Awaitable[dict[str, str]],
]


class RuntimeTestToolUseCase:
    def __init__(
        self,
        runtime_registry: ToolRuntimeRegistry | None = None,
        project_environment_resolver: ProjectEnvironmentResolver | None = None,
    ) -> None:
        self._runtime_registry = runtime_registry
        self._project_environment_resolver = project_environment_resolver

    async def execute(self, input_dto: TestToolInput) -> TestToolOutput:
        if self._runtime_registry is None:
            return TestToolOutput(
                success=False,
                error="Tool runtime is not configured",
            )

        config = input_dto.config
        external_context = dict(input_dto.external_context or {})
        project_environment: dict[str, str] = {}
        environment_keys = collect_project_environment_keys(config)
        environment_keys.update(collect_project_environment_binding_keys(config))

        if environment_keys:
            if input_dto.project_id is None:
                return TestToolOutput(
                    success=False,
                    output={
                        "error_code": "TOOL_PROJECT_ENVIRONMENT_ERROR",
                        "message": "project_id is required when a Tool test references Project Environment",
                    },
                    error="project_id is required when a Tool test references Project Environment",
                )
            if self._project_environment_resolver is None:
                return TestToolOutput(
                    success=False,
                    output={
                        "error_code": "TOOL_PROJECT_ENVIRONMENT_ERROR",
                        "message": "Project Environment resolver is unavailable",
                    },
                    error="Project Environment resolver is unavailable",
                )
            project_environment = await self._project_environment_resolver(
                project_id=input_dto.project_id,
                environment=input_dto.environment,
                keys=environment_keys,
            )

        try:
            runtime_input = apply_context_bindings(
                config,
                input_dto.input_data or {},
                external_context,
                project_environment,
            )
            resolved_config = resolve_tool_templates(
                config,
                external_context=external_context,
                project_environment=project_environment,
            )
        except ToolContextBindingError as exc:
            return TestToolOutput(
                success=False,
                output={
                    "error_code": "TOOL_CONTEXT_BINDING_ERROR",
                    "message": str(exc),
                },
                error=str(exc),
            )
        except ToolTemplateResolutionError as exc:
            return TestToolOutput(
                success=False,
                output={
                    "error_code": "TOOL_TEMPLATE_RESOLUTION_ERROR",
                    "message": str(exc),
                },
                error=str(exc),
            )

        result = await self._runtime_registry.test(
            input_dto.type,
            resolved_config,
            runtime_input,
            timeout_ms=input_dto.timeout_ms or 30000,
        )
        body = result.body
        if body is None and result.output is not None:
            body = json.dumps(result.output)
        return TestToolOutput(
            success=result.success,
            status_code=result.status_code,
            headers=result.headers,
            body=body,
            output=result.output,
            duration_ms=result.duration_ms,
            error=result.error,
        )
