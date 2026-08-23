from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.runtime.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)


class _PreparedExecutionParent:
    def __init__(self, response_format: dict) -> None:
        self.response_format = response_format

    async def _prepare(self, input_dto):
        agent = SimpleNamespace(project_id=input_dto.project_id, id=uuid4())
        return (
            agent,
            None,
            uuid4(),
            None,
            None,
            self.response_format,
            None,
            None,
            None,
            None,
            [],
        )


class _StrictRuntimeHost(InstrumentedPrimaryExecutionMixin, _PreparedExecutionParent):
    pass


@pytest.mark.asyncio
async def test_json_output_is_strict_even_when_saved_flag_is_false() -> None:
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        host = _StrictRuntimeHost(
            {
                "enabled": True,
                "type": "json",
                "strict": False,
                "schema": {"message": "string"},
            }
        )

        await host._prepare(SimpleNamespace(project_id=uuid4()))

        assert context.strict_json is True
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_text_output_does_not_enable_strict_json_validation() -> None:
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        host = _StrictRuntimeHost(
            {
                "enabled": False,
                "type": "text",
                "strict": False,
                "schema": None,
            }
        )

        await host._prepare(SimpleNamespace(project_id=uuid4()))

        assert context.strict_json is False
    finally:
        current_execution.reset(token)
