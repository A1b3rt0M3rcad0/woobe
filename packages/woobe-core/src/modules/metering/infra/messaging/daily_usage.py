from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _increment_daily(
    session: AsyncSession,
    *,
    project_id: UUID,
    agent_id: UUID | None,
    day: date,
    occurred_at: datetime,
    requests: int = 0,
    successful_requests: int = 0,
    failed_requests: int = 0,
    cancelled_requests: int = 0,
    llm_calls: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_calls: int = 0,
    cost_usd: float = 0.0,
    priced_requests: int = 0,
    partial_cost_requests: int = 0,
    unpriced_requests: int = 0,
) -> None:
    params = {
        "project_id": project_id,
        "agent_id": agent_id,
        "day": day,
        "requests": requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "cancelled_requests": cancelled_requests,
        "llm_calls": llm_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": tool_calls,
        "cost_usd": cost_usd,
        "priced_requests": priced_requests,
        "partial_cost_requests": partial_cost_requests,
        "unpriced_requests": unpriced_requests,
        "occurred_at": occurred_at,
        "updated_at": datetime.now(UTC),
    }
    await session.execute(
        text(
            """
            INSERT INTO metering.usage_daily_project (
                project_id, day, requests, successful_requests, failed_requests,
                cancelled_requests, llm_calls, input_tokens, output_tokens,
                embedding_tokens, tool_calls, vector_queries, storage_mb, cost_usd,
                priced_requests, partial_cost_requests, unpriced_requests,
                last_event_occurred_at, updated_at
            ) VALUES (
                :project_id, :day, :requests, :successful_requests, :failed_requests,
                :cancelled_requests, :llm_calls, :input_tokens, :output_tokens,
                0, :tool_calls, 0, 0, :cost_usd,
                :priced_requests, :partial_cost_requests, :unpriced_requests,
                :occurred_at, :updated_at
            )
            ON CONFLICT (project_id, day) DO UPDATE SET
                requests = metering.usage_daily_project.requests + EXCLUDED.requests,
                successful_requests = metering.usage_daily_project.successful_requests + EXCLUDED.successful_requests,
                failed_requests = metering.usage_daily_project.failed_requests + EXCLUDED.failed_requests,
                cancelled_requests = metering.usage_daily_project.cancelled_requests + EXCLUDED.cancelled_requests,
                llm_calls = metering.usage_daily_project.llm_calls + EXCLUDED.llm_calls,
                input_tokens = metering.usage_daily_project.input_tokens + EXCLUDED.input_tokens,
                output_tokens = metering.usage_daily_project.output_tokens + EXCLUDED.output_tokens,
                tool_calls = metering.usage_daily_project.tool_calls + EXCLUDED.tool_calls,
                cost_usd = metering.usage_daily_project.cost_usd + EXCLUDED.cost_usd,
                priced_requests = metering.usage_daily_project.priced_requests + EXCLUDED.priced_requests,
                partial_cost_requests = metering.usage_daily_project.partial_cost_requests + EXCLUDED.partial_cost_requests,
                unpriced_requests = metering.usage_daily_project.unpriced_requests + EXCLUDED.unpriced_requests,
                last_event_occurred_at = GREATEST(
                    metering.usage_daily_project.last_event_occurred_at,
                    EXCLUDED.last_event_occurred_at
                ),
                updated_at = EXCLUDED.updated_at
            """
        ),
        params,
    )
    if agent_id is None:
        return
    await session.execute(
        text(
            """
            INSERT INTO metering.usage_daily_agent (
                agent_id, day, project_id, requests, successful_requests,
                failed_requests, cancelled_requests, llm_calls, input_tokens,
                output_tokens, tool_calls, vector_queries, cost_usd,
                priced_requests, partial_cost_requests, unpriced_requests,
                last_event_occurred_at, updated_at
            ) VALUES (
                :agent_id, :day, :project_id, :requests, :successful_requests,
                :failed_requests, :cancelled_requests, :llm_calls, :input_tokens,
                :output_tokens, :tool_calls, 0, :cost_usd,
                :priced_requests, :partial_cost_requests, :unpriced_requests,
                :occurred_at, :updated_at
            )
            ON CONFLICT (agent_id, day) DO UPDATE SET
                requests = metering.usage_daily_agent.requests + EXCLUDED.requests,
                successful_requests = metering.usage_daily_agent.successful_requests + EXCLUDED.successful_requests,
                failed_requests = metering.usage_daily_agent.failed_requests + EXCLUDED.failed_requests,
                cancelled_requests = metering.usage_daily_agent.cancelled_requests + EXCLUDED.cancelled_requests,
                llm_calls = metering.usage_daily_agent.llm_calls + EXCLUDED.llm_calls,
                input_tokens = metering.usage_daily_agent.input_tokens + EXCLUDED.input_tokens,
                output_tokens = metering.usage_daily_agent.output_tokens + EXCLUDED.output_tokens,
                tool_calls = metering.usage_daily_agent.tool_calls + EXCLUDED.tool_calls,
                cost_usd = metering.usage_daily_agent.cost_usd + EXCLUDED.cost_usd,
                priced_requests = metering.usage_daily_agent.priced_requests + EXCLUDED.priced_requests,
                partial_cost_requests = metering.usage_daily_agent.partial_cost_requests + EXCLUDED.partial_cost_requests,
                unpriced_requests = metering.usage_daily_agent.unpriced_requests + EXCLUDED.unpriced_requests,
                last_event_occurred_at = GREATEST(
                    metering.usage_daily_agent.last_event_occurred_at,
                    EXCLUDED.last_event_occurred_at
                ),
                updated_at = EXCLUDED.updated_at
            """
        ),
        params,
    )
