from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class TraceRecorder(ABC):

    @abstractmethod
    async def create_trace(
        self,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None,
        tenant_id: UUID | None,
        user_id: UUID | None,
        provider: str,
        model: str,
        trace_id: UUID | None = None,
    ) -> UUID:
        ...

    @abstractmethod
    async def record_event(
        self,
        trace_id: UUID,
        project_id: UUID,
        event_type: str,
        latency_ms: float | None = None,
        payload: dict | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def fail_trace(self, trace_id: UUID, error: str) -> None:
        ...

    @abstractmethod
    async def complete_trace(
        self,
        trace_id: UUID,
        answer: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        model: str,
        provider: str,
        latency_ms: float | None = None,
        message_id: UUID | None = None,
        sources: list | None = None,
        parsed_output: dict | None = None,
        output_parse_error: str | None = None,
        tool_calls: list | None = None,
        fallback_used: bool = False,
        fallback_info: dict | None = None,
        json_format_latency_ms: int | None = None,
    ) -> None:
        ...
