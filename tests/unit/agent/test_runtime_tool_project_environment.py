from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import TestToolInput
from modules.agent.application.runtime_tool_use_cases import RuntimeTestToolUseCase
from modules.agent.domain.enums import ToolType


def _result():
    return SimpleNamespace(
        success=True,
        status_code=200,
        headers={},
        body=None,
        output={"ok": True},
        duration_ms=1.0,
        error=None,
    )


@pytest.mark.asyncio
async def test_tool_test_resolves_selected_project_environment_before_transport() -> None:
    project_id = uuid4()
    registry = SimpleNamespace(test=AsyncMock(return_value=_result()))
    resolver = AsyncMock(
        return_value={
            "API_URL": "https://staging.example.com",
            "API_KEY": "staging-secret",
        }
    )
    use_case = RuntimeTestToolUseCase(
        runtime_registry=registry,
        project_environment_resolver=resolver,
    )

    result = await use_case.execute(
        TestToolInput(
            type=ToolType.HTTP,
            project_id=project_id,
            environment="staging",
            config={
                "protocol": "http",
                "url": "{{project_env.API_URL}}/customers",
                "method": "GET",
                "headers": [
                    {
                        "key": "Authorization",
                        "value": "Bearer {{project_env.API_KEY}}",
                    }
                ],
                "bindings": {
                    "tenant_id": {
                        "source": {
                            "kind": "project_environment",
                            "field": "TENANT_ID",
                        }
                    }
                },
            },
            input_data={"tenant_id": "model-value"},
        )
    )

    resolver.assert_awaited_once_with(
        project_id=project_id,
        environment="staging",
        keys={"API_URL", "API_KEY", "TENANT_ID"},
    )
    assert result.success is False
    assert result.output == {
        "error_code": "TOOL_CONTEXT_BINDING_ERROR",
        "message": "Project Environment key 'TENANT_ID' required by Tool binding 'tenant_id' is unavailable",
    }
    registry.test.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_test_resolves_templates_and_authoritative_bindings() -> None:
    project_id = uuid4()
    registry = SimpleNamespace(test=AsyncMock(return_value=_result()))
    resolver = AsyncMock(
        return_value={
            "API_URL": "https://prod.example.com",
            "API_KEY": "prod-secret",
            "TENANT_ID": "tenant-prod",
        }
    )
    use_case = RuntimeTestToolUseCase(
        runtime_registry=registry,
        project_environment_resolver=resolver,
    )

    result = await use_case.execute(
        TestToolInput(
            type=ToolType.HTTP,
            project_id=project_id,
            environment="production",
            config={
                "protocol": "http",
                "url": "{{project_env.API_URL}}/customers/{{external_context.customer_id}}",
                "method": "GET",
                "headers": [
                    {
                        "key": "Authorization",
                        "value": "Bearer {{project_env.API_KEY}}",
                    }
                ],
                "bindings": {
                    "tenant_id": {
                        "source": {
                            "kind": "project_environment",
                            "field": "TENANT_ID",
                        }
                    }
                },
            },
            input_data={"tenant_id": "model-forged"},
            external_context={"customer_id": "cus-1"},
        )
    )

    assert result.success is True
    registry.test.assert_awaited_once()
    call = registry.test.await_args
    assert call.args[0] == ToolType.HTTP
    assert call.args[1]["url"] == "https://prod.example.com/customers/cus-1"
    assert call.args[1]["headers"][0]["value"] == "Bearer prod-secret"
    assert call.args[2]["tenant_id"] == "tenant-prod"


@pytest.mark.asyncio
async def test_tool_test_requires_project_id_only_when_project_environment_is_used() -> None:
    registry = SimpleNamespace(test=AsyncMock(return_value=_result()))
    use_case = RuntimeTestToolUseCase(runtime_registry=registry)

    result = await use_case.execute(
        TestToolInput(
            type=ToolType.HTTP,
            config={
                "protocol": "http",
                "url": "{{project_env.API_URL}}/customers",
                "method": "GET",
            },
        )
    )

    assert result.success is False
    assert result.output is not None
    assert result.output["error_code"] == "TOOL_PROJECT_ENVIRONMENT_ERROR"
    registry.test.assert_not_awaited()
