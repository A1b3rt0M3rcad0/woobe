from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.target_resolver import ResolvedEvaluationTarget
from modules.evaluation.infra.database.models import EvaluationRunModel
from modules.network.application import NetworkApplicationService
from modules.network.domain.enums import NetworkEnvironment
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkMessageModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
)
from modules.observability.infra.database.models import TraceEventModel, TraceModel


_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


class EvaluationRuntimeCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class NetworkRuntimeEvidence:
    output: dict[str, Any]
    metrics: dict[str, Any]
    network_execution_id: UUID
    root_trace_id: UUID | None
    network_session_id: UUID


class EvaluationNetworkRuntimeGateway:
    """Submit Evaluation Network Runs through the canonical Network service."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._service = NetworkApplicationService(session_factory)

    async def execute(
        self,
        *,
        evaluation_run_id: UUID,
        evaluation_trial_id: UUID,
        pair_key: str,
        target_side: str,
        project_id: UUID,
        target: ResolvedEvaluationTarget | Any,
        message: str,
        initial_context: dict[str, Any] | None,
        network_session_id: UUID | None = None,
        turn_position: int = 1,
    ) -> NetworkRuntimeEvidence:
        session = (
            await self._get_session(network_session_id, project_id=project_id)
            if network_session_id is not None
            else None
        )
        if session is None:
            session = await self._create_session(
                target=target,
                project_id=project_id,
                evaluation_trial_id=evaluation_trial_id,
            )
        execution = await self._service.submit_execution(
            network_id=target.entity_id,
            project_id=project_id,
            network_session_id=session.id,
            message=message,
            idempotency_key=f"evaluation:{evaluation_trial_id}:turn:{turn_position}",
            expected_draft_revision=(
                int((target.snapshot or {}).get("draft_revision"))
                if target.source_type == "draft"
                else None
            ),
        )
        await self._attach_evaluation_metadata(
            execution_id=execution.id,
            evaluation_run_id=evaluation_run_id,
            evaluation_trial_id=evaluation_trial_id,
            pair_key=pair_key,
            target_side=target_side,
            initial_context=initial_context,
            turn_position=turn_position,
        )

        timeout_seconds = max(
            1,
            min(int((target.snapshot or {}).get("timeout_seconds") or 300), 900),
        )
        completed = await self._wait_for_completion(
            execution_id=execution.id,
            evaluation_run_id=evaluation_run_id,
            project_id=project_id,
            timeout_seconds=timeout_seconds,
        )
        if completed.status != "completed":
            raise RuntimeError(
                completed.failure_detail
                or completed.failure_code
                or f"Network execution ended as {completed.status}"
            )
        return await self._evidence(completed, network_session_id=session.id)

    async def _get_session(
        self,
        session_id: UUID,
        *,
        project_id: UUID,
    ) -> NetworkSessionModel | None:
        async with self._session_factory() as db:
            row = await db.get(NetworkSessionModel, session_id)
            if row is None or row.project_id != project_id:
                return None
            return row

    async def _create_session(
        self,
        *,
        target,
        project_id: UUID,
        evaluation_trial_id: UUID,
    ) -> NetworkSessionModel:
        if target.source_type == "draft":
            return await self._service.create_session(
                network_id=target.entity_id,
                project_id=project_id,
                environment=NetworkEnvironment.DRAFT,
                title=f"Evaluation {evaluation_trial_id}",
                tenant_id="evaluation",
                user_id=None,
                external_session_id=f"evaluation:{evaluation_trial_id}",
            )

        environment = (
            NetworkEnvironment.STAGING.value
            if target.source_type == "staging"
            else NetworkEnvironment.PRODUCTION.value
        )
        async with self._session_factory() as db, db.begin():
            existing = await db.scalar(
                select(NetworkSessionModel).where(
                    NetworkSessionModel.network_id == target.entity_id,
                    NetworkSessionModel.external_session_id
                    == f"evaluation:{evaluation_trial_id}",
                )
            )
            if existing is not None:
                return existing
            row = NetworkSessionModel(
                network_id=target.entity_id,
                network_version_id=target.network_version_id,
                project_id=project_id,
                environment=environment,
                title=f"Evaluation {evaluation_trial_id}",
                tenant_id="evaluation",
                user_id=None,
                external_session_id=f"evaluation:{evaluation_trial_id}",
                status="active",
            )
            db.add(row)
            await db.flush()
            return row

    async def _attach_evaluation_metadata(
        self,
        *,
        execution_id: UUID,
        evaluation_run_id: UUID,
        evaluation_trial_id: UUID,
        pair_key: str,
        target_side: str,
        initial_context: dict[str, Any] | None,
        turn_position: int,
    ) -> None:
        metadata = {
            "run_purpose": "evaluation",
            "evaluation_run_id": str(evaluation_run_id),
            "evaluation_trial_id": str(evaluation_trial_id),
            "comparison_pair_id": pair_key,
            "target_side": target_side,
            "initial_context": initial_context,
            "evaluation_turn_position": turn_position,
        }
        async with self._session_factory() as db, db.begin():
            message = await db.scalar(
                select(NetworkMessageModel)
                .where(NetworkMessageModel.network_execution_id == execution_id)
                .order_by(NetworkMessageModel.created_at)
                .limit(1)
            )
            if message is not None:
                message.data = {**(message.data or {}), **metadata}
            event = await db.scalar(
                select(NetworkExecutionEventModel)
                .where(NetworkExecutionEventModel.network_execution_id == execution_id)
                .order_by(NetworkExecutionEventModel.sequence)
                .limit(1)
            )
            if event is not None:
                event.payload = {**(event.payload or {}), **metadata}
            outbox = await db.scalar(
                select(NetworkOutboxEventModel)
                .where(NetworkOutboxEventModel.aggregate_id == execution_id)
                .order_by(NetworkOutboxEventModel.created_at)
                .limit(1)
            )
            if outbox is not None:
                outbox.payload = {**(outbox.payload or {}), **metadata}

    async def _wait_for_completion(
        self,
        *,
        execution_id: UUID,
        evaluation_run_id: UUID,
        project_id: UUID,
        timeout_seconds: int,
    ) -> NetworkExecutionModel:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            async with self._session_factory() as db:
                run = await db.get(EvaluationRunModel, evaluation_run_id)
                execution = await db.get(NetworkExecutionModel, execution_id)
                if run is not None and run.cancel_requested_at is not None:
                    await self._service.request_cancellation(execution_id, project_id)
                    raise EvaluationRuntimeCancelled("Evaluation Run was cancelled")
                if execution is not None and execution.status in _TERMINAL:
                    return execution
            await asyncio.sleep(0.5)
        await self._service.request_cancellation(execution_id, project_id)
        raise TimeoutError("Network Evaluation Trial exceeded its timeout")

    async def _evidence(
        self,
        execution: NetworkExecutionModel,
        *,
        network_session_id: UUID,
    ) -> NetworkRuntimeEvidence:
        async with self._session_factory() as db:
            invocations = list(
                (
                    await db.scalars(
                        select(NetworkInvocationModel).where(
                            NetworkInvocationModel.network_execution_id == execution.id
                        )
                    )
                ).all()
            )
            traces = list(
                (
                    await db.scalars(
                        select(TraceModel).where(
                            TraceModel.network_execution_id == execution.id
                        )
                    )
                ).all()
            )
            trace_ids = [trace.id for trace in traces]
            events = (
                list(
                    (
                        await db.scalars(
                            select(TraceEventModel).where(
                                TraceEventModel.trace_id.in_(trace_ids)
                            )
                        )
                    ).all()
                )
                if trace_ids
                else []
            )

        tool_calls = [
            event.payload or {}
            for event in events
            if event.event_type in {"tool_call", "tool_result"}
        ]
        sources: list[dict[str, Any]] = []
        parsed_output = None
        output_parse_error = None
        for trace in traces:
            data = trace.data or {}
            raw_sources = data.get("sources")
            if isinstance(raw_sources, list):
                sources.extend(item for item in raw_sources if isinstance(item, dict))
            if parsed_output is None and isinstance(data.get("parsed_output"), dict):
                parsed_output = data["parsed_output"]
            if output_parse_error is None and data.get("output_parse_error"):
                output_parse_error = str(data["output_parse_error"])

        costs = [
            float(trace.total_cost_usd)
            for trace in traces
            if trace.total_cost_usd is not None
        ]
        input_tokens = sum(
            int((trace.data or {}).get("input_tokens") or 0) for trace in traces
        )
        output_tokens = sum(
            int((trace.data or {}).get("output_tokens") or 0) for trace in traces
        )
        latency_ms = None
        if execution.started_at and execution.completed_at:
            latency_ms = round(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
        output = {
            "answer": execution.output_message or "",
            "parsed_output": parsed_output,
            "output_parse_error": output_parse_error,
            "tool_calls": tool_calls,
            "sources": sources,
        }
        metrics = {
            "latency_ms": latency_ms,
            "cost_usd": sum(costs) if costs else None,
            "input_tokens": input_tokens or None,
            "output_tokens": output_tokens or None,
            "agent_run_count": len(invocations),
            "tool_call_count": len(tool_calls),
            "source_count": len(sources),
            "fallback_used": any(trace.fallback_used for trace in traces),
            "run_purpose": "evaluation",
            "network_execution_status": execution.status,
            "pricing_coverage": (
                "complete"
                if traces and all(trace.total_cost_usd is not None for trace in traces)
                else "partial"
                if costs
                else "unknown"
            ),
        }
        return NetworkRuntimeEvidence(
            output=output,
            metrics=metrics,
            network_execution_id=execution.id,
            root_trace_id=execution.root_trace_id,
            network_session_id=network_session_id,
        )


__all__ = [
    "EvaluationNetworkRuntimeGateway",
    "EvaluationRuntimeCancelled",
    "NetworkRuntimeEvidence",
]
