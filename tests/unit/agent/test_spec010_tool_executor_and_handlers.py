"""Tests for spec 010: tool executor wiring, secret resolver, and self-consumption removal.

Covers: tool result imediato, secret resolution, composer construction,
redaction, no self-loop.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolStatus, ToolType
from modules.agent.runtime.agent_tool_executor import AgentToolExecutor
from modules.agent.infra.messaging.inbox_handlers import AgentInboxEventRouter


class TestAgentToolExecutorWiring:
    """AgentToolExecutor must accept and pass secret_resolver."""

    @pytest.mark.asyncio
    async def test_accepts_secret_resolver(self):
        tool_repo = MagicMock()
        executor = MagicMock()
        secret_resolver = MagicMock()
        instance = AgentToolExecutor(
            tool_repo=tool_repo,
            tool_executor=executor,
            secret_resolver=secret_resolver,
        )
        assert instance._secret_resolver is secret_resolver

    @pytest.mark.asyncio
    async def test_execute_tool_with_secret_resolver(self):
        tool_repo = MagicMock()
        tool_id = uuid4()
        tool = Tool(
            id=tool_id,
            project_id=uuid4(),
            name="Example API",
            type=ToolType.HTTP,
            status=ToolStatus.ACTIVE,
            config={
                "url": "https://api.example.com/{{path}}",
                "method": "POST",
                "headers": [{"key": "Authorization", "value": "Bearer {{secret}}"}],
                "variables": {"path": "test", "secret": "placeholder"},
            },
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        tool_repo.get_by_id = AsyncMock(return_value=tool)
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=MagicMock(success=True, output={}, duration_ms=100, error=None),
        )
        secret_resolver = MagicMock()
        secret_resolver.resolve_headers = AsyncMock(
            return_value={"Authorization": "Bearer resolved-secret"},
        )

        instance = AgentToolExecutor(
            tool_repo=tool_repo,
            tool_executor=executor,
            secret_resolver=secret_resolver,
        )
        result = await instance.execute_tool(tool_id, {"path": "test"})
        assert isinstance(result, dict)
        secret_resolver.resolve_headers.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_tool_without_secret_resolver(self):
        tool_repo = MagicMock()
        tool_id = uuid4()
        tool = Tool(
            id=tool_id,
            project_id=uuid4(),
            name="Example API",
            type=ToolType.HTTP,
            status=ToolStatus.ACTIVE,
            config={
                "url": "https://api.example.com/test",
                "method": "GET",
                "headers": [],
            },
            input_schema={"type": "object", "properties": {}, "required": []},
        )
        tool_repo.get_by_id = AsyncMock(return_value=tool)

        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=MagicMock(success=True, output={}, duration_ms=50, error=None),
        )

        instance = AgentToolExecutor(
            tool_repo=tool_repo,
            tool_executor=executor,
        )
        result = await instance.execute_tool(tool_id, {})
        assert isinstance(result, dict)


class TestNoSelfConsumption:
    """Agent must not register handlers that consume its own events."""

    def test_inbox_router_has_no_tool_event_handlers(self):
        router = AgentInboxEventRouter()
        assert router.registered_event_types == []
        assert not hasattr(router, "register_tool_handlers")

    def test_no_agent_tool_handler_constants_imported(self):
        import ast
        import inspect
        source = inspect.getsource(AgentInboxEventRouter)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id in ("AGENT_TOOL_EVENT_HANDLERS", "TOOLS_LEGACY_EVENT_MAP"):
                    pytest.fail(f"Self-consumption constant {node.id} still present")


class TestComposerConstruction:
    """Tool composers must wire use cases with correct signatures."""

    def test_execute_tool_composer_includes_secret_resolver(self):
        import inspect
        from modules.agent.composition.composers.tools_composers import execute_tool_composer
        source = inspect.getsource(execute_tool_composer)
        assert "secret_resolver" in source

    def test_create_tool_composer_includes_outbox(self):
        import inspect
        from modules.agent.composition.composers.tools_composers import create_tool_composer
        source = inspect.getsource(create_tool_composer)
        assert "outbox" in source

    def test_agent_tool_executor_imports_execute_tool_use_case(self):
        import inspect
        from modules.agent.runtime.agent_tool_executor import AgentToolExecutor
        source = inspect.getsource(AgentToolExecutor)
        assert "ExecuteToolUseCase" in source
