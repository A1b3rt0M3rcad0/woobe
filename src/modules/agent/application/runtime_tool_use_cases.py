from __future__ import annotations

import json

from modules.agent.application.dtos.tools_dtos import (
    ExecuteToolInput,
    ExecuteToolOutput,
    TestToolInput,
    TestToolOutput,
)
from modules.agent.application.interfaces.ports import ToolExecutionPort, ToolSecretResolverPort
from modules.agent.application.tool_runtime import (
    ToolRuntimeRegistry,
    build_default_tool_runtime_registry,
)
from modules.agent.domain.enums import ToolStatus
from modules.agent.domain.errors import ToolNotFoundError
from modules.agent.application.interfaces.repositories import ToolRepository


class RuntimeExecuteToolUseCase:
    def __init__(
        self,
        tool_repo: ToolRepository,
        tool_executor: ToolExecutionPort | None = None,
        secret_resolver: ToolSecretResolverPort | None = None,
        runtime_registry: ToolRuntimeRegistry | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._tool_executor = tool_executor
        self._secret_resolver = secret_resolver
        self._runtime_registry = runtime_registry

    async def execute(self, input_dto: ExecuteToolInput) -> ExecuteToolOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool.status != ToolStatus.ACTIVE:
            raise ToolNotFoundError(input_dto.tool_id)

        registry = self._runtime_registry
        if registry is None:
            if self._tool_executor is None:
                return ExecuteToolOutput(success=False, error="Tool runtime is not configured")
            registry = build_default_tool_runtime_registry(
                self._tool_executor,
                self._secret_resolver,
            )

        result = await registry.execute(tool, input_dto.input_data or {})
        return ExecuteToolOutput(
            success=result.success,
            output=result.output,
            duration_ms=result.duration_ms,
            error=result.error,
        )


class RuntimeTestToolUseCase:
    def __init__(
        self,
        tool_executor: ToolExecutionPort | None = None,
        runtime_registry: ToolRuntimeRegistry | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._runtime_registry = runtime_registry

    async def execute(self, input_dto: TestToolInput) -> TestToolOutput:
        registry = self._runtime_registry
        if registry is None:
            if self._tool_executor is None:
                return TestToolOutput(success=False, error="Tool runtime is not configured")
            registry = build_default_tool_runtime_registry(self._tool_executor)

        result = await registry.test(
            input_dto.type,
            input_dto.config,
            input_dto.input_data or {},
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
