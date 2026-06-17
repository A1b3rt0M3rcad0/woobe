from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, AsyncGenerator
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.agent.application.use_cases.tools_use_cases import ExecuteToolUseCase
from modules.agent.domain.ports.llm_factory import LLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings

logger = logging.getLogger(__name__)


class AskAgentStreamService:
    """SSE adapter over the canonical Agent execution use case.

    The canonical use case owns persistence and emits the Agent Outbox events in
    the same transaction. Reusing it here prevents the streaming and non-streaming
    paths from diverging on structured output, Tool calls, fallback and trace data.
    """

    def __init__(
        self,
        session_factory: Callable[..., Any],
        llm_factory: LLMFactory,
    ) -> None:
        self._session_factory = session_factory
        settings = Settings()
        self._cipher = SecretCipherAdapter(settings.encryption_key)
        self._http_executor = HttpToolExecutor()
        self._use_case = AskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=self._execute_tool,
        )

    async def _execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        async with AgentUnitOfWork(self._session_factory) as uow:
            resolver = ToolSecretResolverAdapter(uow.tool_secrets, self._cipher)
            use_case = ExecuteToolUseCase(
                tool_repo=uow.tools,
                tool_executor=self._http_executor,
                secret_resolver=resolver,
            )
            result = await use_case.execute(
                ExecuteToolInput(tool_id=tool_id, input_data=input_data)
            )
            return result.model_dump()

    async def generate(self, input_dto: AskInput) -> AsyncGenerator[str, None]:
        try:
            output = await self._use_case.execute(input_dto)
        except Exception as exc:
            logger.exception("Agent streaming execution failed: %s", exc)
            yield self._sse_event("error", {"message": str(exc)})
            return

        if output.sources:
            yield self._sse_event(
                "sources",
                {"sources": [source.model_dump() for source in output.sources]},
            )

        yield self._sse_event(
            "meta",
            {
                "session_id": str(output.session_id) if output.session_id else None,
                "trace_id": str(output.trace_id) if output.trace_id else None,
            },
        )

        for tool_call in output.tool_calls or []:
            yield self._sse_event(
                "tool_call",
                {
                    "tool_call_id": tool_call.tool_call_id,
                    "tool_name": tool_call.tool_name,
                    "input": tool_call.input,
                    "output": tool_call.output,
                    "duration_ms": tool_call.duration_ms,
                    "success": tool_call.success,
                    "error": tool_call.error,
                },
            )

        if output.answer:
            yield self._sse_event("token", {"content": output.answer})

        yield self._sse_event(
            "done",
            {
                "answer": output.answer,
                "session_id": str(output.session_id) if output.session_id else None,
                "message_id": str(output.message_id) if output.message_id else None,
                "usage": output.usage.model_dump() if output.usage else None,
                "sources": [source.model_dump() for source in output.sources],
                "model": output.model,
                "provider": output.provider,
                "latency_ms": output.latency_ms,
                "trace_id": str(output.trace_id) if output.trace_id else None,
                "parsed_output": output.parsed_output,
                "output_parse_error": output.output_parse_error,
                "fallback_used": output.fallback_used,
                "fallback_info": output.fallback_info,
                "tool_calls": [tool.model_dump() for tool in output.tool_calls],
            },
        )

    @staticmethod
    def _sse_event(event_type: str, data: dict[str, Any]) -> str:
        payload = {"type": event_type, **data}
        return f"data: {json.dumps(payload, default=str)}\n\n"
