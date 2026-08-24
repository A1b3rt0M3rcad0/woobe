from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from modules.agent.application.interfaces.http_tool_contract import (
    compile_http_tool_group_contract,
)
from modules.agent.application.interfaces.tool_runtime import MCP_REMOTE_TOOL_INPUT_KEY
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolStatus, ToolType
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.execution.agent_tool_executor import AgentToolExecutor


PRIVATE_BASE_URL = "http://192.168.1.8:3001"
ROUTE_ID = "route-search-contacts"


def _grouped_http_tool(tool_id):
    compiled = compile_http_tool_group_contract(
        {
            "protocol": "http",
            "mode": "group",
            "schema_version": 2,
            "base_url": PRIVATE_BASE_URL,
            "headers": [],
            "routes": [
                {
                    "id": ROUTE_ID,
                    "operation_id": "search_contacts",
                    "name": "Search contacts",
                    "method": "POST",
                    "path": "/v1/tools/whatsapp/search-contacts",
                    "body": '{"query":"{{query}}"}',
                    "risk_level": "low",
                    "status": "active",
                    "default_permission": "allow",
                }
            ],
        }
    )
    return Tool(
        id=tool_id,
        project_id=uuid4(),
        name="Local contacts",
        type=ToolType.HTTP,
        status=ToolStatus.ACTIVE,
        config=compiled.config,
    )


@pytest.mark.asyncio
async def test_agent_runtime_preserves_local_network_http_executor_for_private_target():
    tool_id = uuid4()
    tool_repo = MagicMock()
    tool_repo.get_by_id = AsyncMock(return_value=_grouped_http_tool(tool_id))
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"contacts": [{"name": "Wesley"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    executor = HttpToolExecutor(client=client, allow_local_networks=True)
    runtime = AgentToolExecutor(tool_repo=tool_repo, tool_executor=executor)

    try:
        result = await runtime.execute_tool(
            tool_id,
            {
                MCP_REMOTE_TOOL_INPUT_KEY: ROUTE_ID,
                "query": "Wesley",
            },
        )
    finally:
        await client.aclose()

    assert result["success"] is True
    assert len(requests) == 1
    assert str(requests[0].url) == (
        f"{PRIVATE_BASE_URL}/v1/tools/whatsapp/search-contacts"
    )
    assert requests[0].method == "POST"
    assert json.loads(requests[0].content) == {"query": "Wesley"}


@pytest.mark.asyncio
async def test_agent_runtime_reports_ssrf_block_when_private_target_is_not_allowed():
    tool_id = uuid4()
    tool_repo = MagicMock()
    tool_repo.get_by_id = AsyncMock(return_value=_grouped_http_tool(tool_id))
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    executor = HttpToolExecutor(client=client, allow_local_networks=False)
    runtime = AgentToolExecutor(tool_repo=tool_repo, tool_executor=executor)

    try:
        result = await runtime.execute_tool(
            tool_id,
            {
                MCP_REMOTE_TOOL_INPUT_KEY: ROUTE_ID,
                "query": "Wesley",
            },
        )
    finally:
        await client.aclose()

    assert result["success"] is False
    assert "SSRF blocked" in str(result["error"])
    assert requests == []
