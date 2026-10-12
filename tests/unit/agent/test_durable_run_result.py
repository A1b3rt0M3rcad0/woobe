from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.domain.enums import MessageRole
from modules.agent.domain.errors import MessageNotFoundError
from modules.agent.infra.execution.durable_run_result import durable_run_result
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", [None, "id", "project_id", "agent_id", "session_id", "role"])
async def test_legacy_output_is_read_from_exact_authorized_message(mismatch):
    run = SimpleNamespace(output_message_id=uuid4(), project_id=uuid4(), agent_id=uuid4(),
                          session_id=uuid4(), result={"answer_length": 5})
    message = SimpleNamespace(id=run.output_message_id, project_id=run.project_id,
                              agent_id=run.agent_id, session_id=run.session_id,
                              role=MessageRole.ASSISTANT, content="final")
    repositories = SimpleNamespace(messages=SimpleNamespace(get_by_id=AsyncMock(return_value=message)))
    if mismatch:
        setattr(message, mismatch, MessageRole.USER if mismatch == "role" else uuid4())
        with pytest.raises(ConflictError):
            await durable_run_result(repositories, run)
    else:
        assert await durable_run_result(repositories, run) == {"answer_length": 5, "answer": "final"}
    repositories.messages.get_by_id.assert_awaited_once_with(run.output_message_id)
    assert run.result == {"answer_length": 5}  # observation never persists or changes summaries


@pytest.mark.asyncio
async def test_answer_already_retained_or_deleted_message_never_selects_another_turn():
    read = AsyncMock(side_effect=MessageNotFoundError("missing"))
    repositories = SimpleNamespace(messages=SimpleNamespace(get_by_id=read))
    run = SimpleNamespace(output_message_id=uuid4(), result={"answer": ""})
    assert await durable_run_result(repositories, run) == {"answer": ""}
    read.assert_not_awaited()
    run.result = {"answer_length": 5}
    assert await durable_run_result(repositories, run) == run.result
    assert read.await_count == 1
