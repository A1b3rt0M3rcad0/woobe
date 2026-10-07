from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import (
    AskOutput,
    ToolCallInfo,
    SourceInfo,
)
from modules.agent.presentation.controllers.ask_agent_controller import (
    AskAgentController,
)
from shared.presentation.contracts import OperationRequest


@pytest.mark.asyncio
async def test_http_runtime_serializes_native_tool_and_knowledge_evidence():
    result = AskOutput(
        answer="Completed",
        tool_calls=[
            ToolCallInfo(
                tool_call_id="call-native",
                tool_name="lookup",
                status="completed",
                success=True,
                output={"ready": True},
            )
        ],
        sources=[
            SourceInfo(
                document_id=str(uuid4()),
                document_title="Policy",
                content_preview="Grounding",
            )
        ],
    )
    controller = AskAgentController(
        SimpleNamespace(execute=AsyncMock(return_value=result))
    )
    response = await controller.handle(
        OperationRequest(
            body={
                "project_id": str(uuid4()),
                "agent_id": str(uuid4()),
                "message": "Hello",
            }
        )
    )
    assert response.outcome == "success"
    call = response.body["data"]["tool_calls"][0]
    assert call["tool_call_id"] == "call-native"
    assert call["status"] == "completed" and call["success"] is True
    assert response.body["data"]["sources"][0]["document_title"] == "Policy"
