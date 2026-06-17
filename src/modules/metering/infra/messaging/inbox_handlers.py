from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.infra.database.repositories import (
    SQLAlchemyUsageDailyAgentRepository,
    SQLAlchemyUsageDailyProjectRepository,
    SQLAlchemyUsageEventRepository,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _get_project_id(payload: dict) -> UUID | None:
    raw = payload.get("project_id") or payload.get("agent_id")
    if raw:
        return UUID(raw) if isinstance(raw, str) else raw
    return None


def _get_agent_id(payload: dict) -> UUID | None:
    raw = payload.get("agent_id") or payload.get("execution_id")
    if raw:
        return UUID(raw) if isinstance(raw, str) else raw
    return None


async def handle_noop(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    logger.debug("No-op handler for event_type=%s", event_type)


async def handle_execution_started(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping execution_started handler")
        return
    project_id = _get_project_id(payload) or UUID(int=0)
    agent_id = _get_agent_id(payload)

    logger.info(
        "Recorded execution_started usage for project=%s, agent=%s, trace=%s",
        project_id, agent_id, payload.get("trace_id"),
    )


async def handle_llm_request(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping llm_request handler")
        return
    event_repo = SQLAlchemyUsageEventRepository(session)
    project_repo = SQLAlchemyUsageDailyProjectRepository(session)
    agent_repo = SQLAlchemyUsageDailyAgentRepository(session)

    project_id = _get_project_id(payload) or UUID(int=0)
    agent_id = _get_agent_id(payload)
    input_tokens = payload.get("input_tokens", 0)
    output_tokens = payload.get("output_tokens", 0)
    cost = payload.get("cost_usd", 0.0)
    today = _today()

    await event_repo.save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            event_type=UsageEventType.llm_request,
            quantity=float(input_tokens + output_tokens),
            unit=UsageUnit.token,
            cost_usd=float(cost),
            data={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )
    )

    existing_project = await project_repo.get_by_project_and_day(project_id, today.isoformat())
    if existing_project:
        existing_project.input_tokens += input_tokens
        existing_project.output_tokens += output_tokens
        existing_project.cost_usd += float(cost)
        await project_repo.save(existing_project)
    else:
        await project_repo.save(
            UsageDailyProject(
                project_id=project_id,
                day=today,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=float(cost),
                updated_at=datetime.now(timezone.utc),
            )
        )

    if agent_id:
        existing_agent = await agent_repo.get_by_agent_and_day(agent_id, today.isoformat())
        if existing_agent:
            existing_agent.input_tokens += input_tokens
            existing_agent.output_tokens += output_tokens
            existing_agent.cost_usd += float(cost)
            await agent_repo.save(existing_agent)
        else:
            await agent_repo.save(
                UsageDailyAgent(
                    agent_id=agent_id,
                    project_id=project_id,
                    day=today,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=float(cost),
                    updated_at=datetime.now(timezone.utc),
                )
            )

    logger.info(
        "Recorded llm_request usage: %d in / %d out tokens for project=%s",
        input_tokens, output_tokens, project_id,
    )


async def handle_tool_execution(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping tool_execution handler")
        return
    event_repo = SQLAlchemyUsageEventRepository(session)
    project_repo = SQLAlchemyUsageDailyProjectRepository(session)
    agent_repo = SQLAlchemyUsageDailyAgentRepository(session)

    project_id = _get_project_id(payload) or UUID(int=0)
    agent_id = _get_agent_id(payload)
    today = _today()

    await event_repo.save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            event_type=UsageEventType.tool_call,
            quantity=1.0,
            unit=UsageUnit.call,
            data={"tool_id": payload.get("tool_id"), "tool_name": payload.get("tool_name")},
        )
    )

    existing_project = await project_repo.get_by_project_and_day(project_id, today.isoformat())
    if existing_project:
        existing_project.tool_calls += 1
        await project_repo.save(existing_project)
    else:
        await project_repo.save(
            UsageDailyProject(
                project_id=project_id,
                day=today,
                tool_calls=1,
                updated_at=datetime.now(timezone.utc),
            )
        )

    if agent_id:
        existing_agent = await agent_repo.get_by_agent_and_day(agent_id, today.isoformat())
        if existing_agent:
            existing_agent.tool_calls += 1
            await agent_repo.save(existing_agent)
        else:
            await agent_repo.save(
                UsageDailyAgent(
                    agent_id=agent_id,
                    project_id=project_id,
                    day=today,
                    tool_calls=1,
                    updated_at=datetime.now(timezone.utc),
                )
            )

    logger.info("Recorded tool_execution usage for project=%s", project_id)


async def handle_execution_completed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping execution_completed handler")
        return
    logger.info("Execution completed for execution_id=%s", payload.get("execution_id"))


async def handle_execution_failed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping execution_failed handler")
        return
    logger.info(
        "Execution failed for execution_id=%s, error=%s",
        payload.get("execution_id"), payload.get("error"),
    )


async def handle_fallback(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping fallback handler")
        return
    event_repo = SQLAlchemyUsageEventRepository(session)

    project_id = _get_project_id(payload) or UUID(int=0)
    agent_id = _get_agent_id(payload)

    await event_repo.save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            event_type=UsageEventType.llm_request,
            quantity=1.0,
            unit=UsageUnit.request,
            data={"event_type": event_type, "source": "fallback_triggered"},
        )
    )
    logger.info("Recorded fallback usage for project=%s", project_id)


HANDLER_MAP: dict[str, EventHandler] = {
    "agent.execution.requested.v1": handle_noop,
    "agent.execution.started.v1": handle_execution_started,
    "agent.execution.llm_completed.v1": handle_llm_request,
    "agent.execution.tool_completed.v1": handle_tool_execution,
    "agent.execution.fallback_triggered.v1": handle_fallback,
    "agent.execution.completed.v1": handle_execution_completed,
    "agent.execution.failed.v1": handle_execution_failed,
}


class MeteringInboxEventRouter:
    def __init__(self, handlers: dict[str, EventHandler] | None = None) -> None:
        self._handlers: dict[str, EventHandler] = handlers or dict(HANDLER_MAP)

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type] = handler

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        handler = self._handlers.get(event_type)
        if handler is None:
            logger.warning(
                "No handler registered for event_type=%s, skipping",
                event_type,
            )
            return
        await handler(event_type=event_type, payload=payload, **kwargs)

    @property
    def registered_event_types(self) -> list[str]:
        return list(self._handlers.keys())
