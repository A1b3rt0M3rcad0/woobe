from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.enums import ToolStatus
from modules.agent.infra.execution import agent_tool_runtime_gateway as gateway_module
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from shared.infra.crypto import encrypt_secret
from shared.project_environment import PreparedProjectEnvironmentValue


def _binding(field: str) -> dict:
    return {"source": {"kind": "context", "field": field}}


def _project_environment_binding(field: str) -> dict:
    return {"source": {"kind": "project_environment", "field": field}}


@pytest.mark.asyncio
async def test_gateway_overwrites_model_argument_with_frozen_external_context(
    monkeypatch,
) -> None:
    tool_id = uuid4()
    tool = SimpleNamespace(
        id=tool_id,
        status=ToolStatus.ACTIVE,
        config={"bindings": {"customer_id": _binding("customer_id")}},
    )
    captured: dict = {}

    class Registry:
        async def execute(self, runtime_tool, input_data):
            assert runtime_tool is not tool
            assert runtime_tool.config == tool.config
            captured.update(input_data)
            return SimpleNamespace(
                success=True,
                output={"accepted": True},
                duration_ms=1.0,
                error=None,
            )

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        lambda **_kwargs: Registry(),
    )
    monkeypatch.setattr(
        gateway_module,
        "record_tool_provider_latency",
        lambda _duration_ms: None,
    )

    context = new_execution_context()
    context.prepared_tools = {str(tool_id): tool}
    context.external_context_snapshot = {"customer_id": "trusted-customer"}
    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(),
            executor=SimpleNamespace(),
        )
        result = await gateway.execute_tool(
            tool_id,
            {
                "customer_id": "model-forged-value",
                "query": "recent orders",
            },
        )
    finally:
        current_execution.reset(token)

    assert result["success"] is True
    assert captured == {
        "customer_id": "trusted-customer",
        "query": "recent orders",
    }


@pytest.mark.asyncio
async def test_gateway_overwrites_model_argument_with_project_environment(
    monkeypatch,
) -> None:
    tool_id = uuid4()
    tool = SimpleNamespace(
        id=tool_id,
        status=ToolStatus.ACTIVE,
        config={"bindings": {"api_key": _project_environment_binding("API_KEY")}},
    )
    captured: dict = {}

    class Registry:
        async def execute(self, runtime_tool, input_data):
            captured.update(input_data)
            return SimpleNamespace(
                success=True,
                output={"accepted": True},
                duration_ms=1.0,
                error=None,
            )

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        lambda **_kwargs: Registry(),
    )
    monkeypatch.setattr(
        gateway_module,
        "record_tool_provider_latency",
        lambda _duration_ms: None,
    )

    context = new_execution_context()
    context.prepared_tools = {str(tool_id): tool}
    context.external_context_snapshot = {}
    context.prepared_project_environment = {
        "API_KEY": PreparedProjectEnvironmentValue(
            kind="secret",
            stored_value=encrypt_secret("runtime-secret", "test-encryption-key"),
        ),
        "UNUSED": object(),
    }
    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(encryption_key="test-encryption-key"),
            executor=SimpleNamespace(),
        )
        result = await gateway.execute_tool(
            tool_id,
            {"api_key": "model-forged-value", "query": "recent orders"},
        )
    finally:
        current_execution.reset(token)

    assert result["success"] is True
    assert captured == {
        "api_key": "runtime-secret",
        "query": "recent orders",
    }


@pytest.mark.asyncio
async def test_gateway_returns_deterministic_failure_when_bound_context_is_missing(
    monkeypatch,
) -> None:
    tool_id = uuid4()
    tool = SimpleNamespace(
        id=tool_id,
        status=ToolStatus.ACTIVE,
        config={"bindings": {"customer_id": _binding("customer_id")}},
    )

    def _registry_must_not_be_built(**_kwargs):
        raise AssertionError("Tool provider must not run when context binding cannot resolve")

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        _registry_must_not_be_built,
    )

    context = new_execution_context()
    context.prepared_tools = {str(tool_id): tool}
    context.external_context_snapshot = {}
    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(),
            executor=SimpleNamespace(),
        )
        result = await gateway.execute_tool(tool_id, {})
    finally:
        current_execution.reset(token)

    assert result["success"] is False
    assert result["output"]["error_code"] == "TOOL_CONTEXT_BINDING_ERROR"
    assert "customer_id" in result["error"]
