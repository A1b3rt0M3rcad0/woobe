import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.use_cases.structured_output_ask_use_case import StructuredOutputAskAgentUseCase
from modules.agent.application.use_cases.tools_use_cases import ExecuteToolUseCase
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings

logger = logging.getLogger(__name__)


class AskAgentStreamService:
    def __init__(self, session_factory, llm_factory):
        self._session_factory = session_factory
        settings = Settings()
        self._cipher = SecretCipherAdapter(settings.encryption_key)
        self._http_executor = HttpToolExecutor()
        self._use_case = StructuredOutputAskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=self._execute_tool,
        )

    async def _execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        async with AgentUnitOfWork(self._session_factory) as uow:
            resolver = ToolSecretResolverAdapter(uow.tool_secrets, self._cipher)
            result = await ExecuteToolUseCase(
                tool_repo=uow.tools,
                tool_executor=self._http_executor,
                secret_resolver=resolver,
            ).execute(ExecuteToolInput(tool_id=tool_id, input_data=input_data))
            return result.model_dump()

    async def generate(self, input_dto: AskInput):
        metadata = dict(input_dto.metadata or {})
        metadata.setdefault("server_received_at", datetime.now(timezone.utc).isoformat())
        input_dto = input_dto.model_copy(update={"metadata": metadata})
        try:
            output = await self._use_case.execute(input_dto)
        except Exception as exc:
            logger.exception("Agent streaming execution failed: %s", exc)
            yield self._sse_event("error", {"message": str(exc)})
            return

        yield self._sse_event("meta", {
            "session_id": str(output.session_id) if output.session_id else None,
            "trace_id": str(output.trace_id) if output.trace_id else None,
            "occurred_at": metadata["server_received_at"],
        })
        for event in getattr(output, "execution_events", []) or []:
            yield self._sse_event("trace_event", {"event": event})
        if output.sources:
            yield self._sse_event("sources", {
                "sources": [source.model_dump() for source in output.sources]
            })
        if output.answer:
            yield self._sse_event("token", {
                "content": output.answer,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "synthetic_full_answer": True,
            })
        yield self._sse_event("done", {
            "answer": output.answer,
            "session_id": str(output.session_id) if output.session_id else None,
            "message_id": str(output.message_id) if output.message_id else None,
            "usage": output.usage.model_dump() if output.usage else None,
            "sources": [source.model_dump() for source in output.sources],
            "tool_calls": [tool.model_dump() for tool in output.tool_calls],
            "trace_id": str(output.trace_id) if output.trace_id else None,
            "model": output.model,
            "provider": output.provider,
            "latency_ms": output.latency_ms,
            "fallback_used": output.fallback_used,
            "fallback_info": output.fallback_info,
            "parsed_output": output.parsed_output,
            "output_parse_error": output.output_parse_error,
            "execution_events": getattr(output, "execution_events", []),
            "diagnostics": getattr(output, "diagnostics", None),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })

    @staticmethod
    def _sse_event(event_type, data):
        return f"data: {json.dumps({'type': event_type, **data}, default=str)}\n\n"
