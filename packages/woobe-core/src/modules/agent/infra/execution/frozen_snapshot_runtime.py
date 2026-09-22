from __future__ import annotations

import json
from contextvars import ContextVar
from copy import deepcopy
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.application.dtos.runtime_dtos import UsageInfo
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.use_cases.trace_event_builder import build_execution_timeline_events
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.domain.system_instructions import assemble_canonical_system_instructions
from modules.agent.infra.execution.deferred_run_metrics import build_deferred_agent_metrics
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)
from shared.contracts.errors import ValidationError

_rerun_input_message_id: ContextVar[UUID | None] = ContextVar(
    "rerun_input_message_id",
    default=None,
)


def _uuid_or_none(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _role_value(message: Any) -> str:
    role = getattr(message, "role", None)
    return str(getattr(role, "value", role) or "")


def _session_context_metadata(message: Any) -> dict[str, Any]:
    return {
        "woobe_context": {
            "source_type": "SESSION",
            "source_ref": str(message.id),
            "parent_ref": str(message.session_id),
            "selection_method": "session_history",
            "trust": "session_history",
            "sensitivity": "internal",
        }
    }


def _validate_reused_input_message(
    message: Any,
    *,
    message_id: UUID,
    session: Any,
    agent: Any,
    content: str,
) -> None:
    if message is None or getattr(message, "id", None) != message_id:
        raise ValidationError("Rerun input message was not found")
    if getattr(message, "session_id", None) != session.id:
        raise ValidationError("Rerun input message does not belong to this Session")
    if getattr(message, "project_id", None) != session.project_id:
        raise ValidationError("Rerun input message does not belong to this Project")
    if getattr(message, "agent_id", None) != agent.id:
        raise ValidationError("Rerun input message does not belong to this Agent")
    if _role_value(message) != "user":
        raise ValidationError("Rerun input message must be a user message")
    if getattr(message, "content", None) != content:
        raise ValidationError("Rerun input message content does not match the original Run")


def _messages_to_history(messages: list[Any]) -> list[Any]:
    history: list[Any] = []
    for message in messages:
        role = _role_value(message)
        message_metadata = _session_context_metadata(message)
        if role == "user":
            history.append(
                HumanMessage(
                    content=message.content,
                    additional_kwargs=message_metadata,
                )
            )
            continue
        if role != "assistant":
            continue

        raw_tool_calls = (message.data or {}).get("tool_calls") or []
        tool_calls = [
            {
                "id": tool_call["tool_call_id"],
                "name": tool_call["tool_name"],
                "args": tool_call.get("input", {}),
            }
            for tool_call in raw_tool_calls
            if tool_call.get("tool_call_id")
        ]
        history.append(
            AIMessage(
                content=message.content,
                tool_calls=tool_calls,
                additional_kwargs=message_metadata,
            )
            if tool_calls
            else AIMessage(
                content=message.content,
                additional_kwargs=message_metadata,
            )
        )
        for tool_call in raw_tool_calls:
            if tool_call.get("tool_call_id") and tool_call.get("output") is not None:
                history.append(
                    ToolMessage(
                        content=json.dumps(tool_call["output"]),
                        tool_call_id=tool_call["tool_call_id"],
                        additional_kwargs={
                            "woobe_context": {
                                "source_type": "TOOL",
                                "source_ref": str(tool_call["tool_call_id"]),
                                "parent_ref": str(message.id),
                                "selection_method": "session_tool_history",
                                "trust": "session_history",
                                "sensitivity": "internal",
                            }
                        },
                    )
                )
    return history


class FrozenSnapshotStructuredOutputRuntime(TransactionBoundedStructuredOutputRuntime):
    """Apply frozen rerun state and preserve original Session input provenance."""

    async def _prepare(self, input_dto):
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        raw_message_id = metadata.get("reuse_input_message_id")
        reuse_message_id = None
        if raw_message_id:
            try:
                reuse_message_id = _uuid_or_none(raw_message_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Rerun input message id is invalid") from exc

        token = _rerun_input_message_id.set(reuse_message_id)
        try:
            return await super()._prepare(input_dto)
        finally:
            _rerun_input_message_id.reset(token)

    async def _load_history(self, message_repo, session):
        reuse_message_id = _rerun_input_message_id.get()
        if reuse_message_id is None:
            return await super()._load_history(message_repo, session)

        messages = list(await message_repo.list_by_session(session.id))
        for index, message in enumerate(messages):
            if getattr(message, "id", None) != reuse_message_id:
                continue
            if getattr(message, "session_id", None) != session.id:
                raise ValidationError(
                    "Rerun input message does not belong to the selected Session"
                )
            # Recreate the model context exactly as it existed immediately before
            # the original user input. The input itself is appended by _build_messages.
            return _messages_to_history(messages[:index])
        raise ValidationError(
            "Rerun input message is outside the available Session history"
        )

    async def _save_user_message(
        self,
        session_repo,
        message_repo,
        session,
        content,
        agent,
    ):
        reuse_message_id = _rerun_input_message_id.get()
        if reuse_message_id is None:
            return await super()._save_user_message(
                session_repo,
                message_repo,
                session,
                content,
                agent,
            )

        original = await message_repo.get_by_id(reuse_message_id)
        _validate_reused_input_message(
            original,
            message_id=reuse_message_id,
            session=session,
            agent=agent,
            content=content,
        )
        context = current_execution.get()
        if context is not None:
            context.input_message_id = original.id
        return original

    async def _finalize(
        self,
        session,
        agent,
        input_dto,
        trace_id,
        answer,
        usage,
        response_model,
        response_provider,
        llm_latency_ms,
        sources,
        parsed_output,
        output_parse_error,
        tool_calls_recorded,
        fallback_used,
        fallback_info_result,
        json_format_latency_ms,
    ):
        output = await super()._finalize(
            session,
            agent,
            input_dto,
            trace_id,
            answer,
            usage,
            response_model,
            response_provider,
            llm_latency_ms,
            sources,
            parsed_output,
            output_parse_error,
            tool_calls_recorded,
            fallback_used,
            fallback_info_result,
            json_format_latency_ms,
        )

        context = current_execution.get()
        if (
            context is None
            or not getattr(context, "defer_persistence", False)
            or context.execution is None
        ):
            return output

        # The Agent runtime owns AgentRun telemetry. Network only transports this
        # immutable snapshot to Redis and materializes it in the bulk finalizer.
        metrics = build_deferred_agent_metrics(context, output)
        output.usage = UsageInfo.model_validate(metrics.usage)
        output.diagnostics = metrics.diagnostics
        output.execution_events = build_execution_timeline_events(
            str(output.trace_id or context.trace_id),
            context=context,
            timeline=list(context.execution.timeline),
            completed_at=metrics.completed_at,
            total_latency_ms=metrics.total_latency_ms,
            output_parse_error=output.output_parse_error,
            completion_attributes={"diagnostics": metrics.diagnostics},
            include_http_boundaries=False,
        )
        object.__setattr__(output, "llm_calls", metrics.llm_calls)
        object.__setattr__(output, "run_started_at", metrics.started_at)
        object.__setattr__(output, "run_completed_at", metrics.completed_at)
        return output

    def _apply_snapshot_override(self, agent, snapshot: dict):
        # Do not call the compatibility implementation from AskAgentUseCase here.
        # Rerun needs exact replacement semantics, including explicit nulls, and
        # must use the Agent SessionMode enum (stateful/stateless).
        for field in ("name", "description"):
            if snapshot.get(field) is not None:
                setattr(agent, field, snapshot[field])
        if "behavior_spec" in snapshot or "system_prompt" in snapshot:
            agent.behavior_spec = deepcopy(snapshot.get("behavior_spec"))
        if "system_prompt" in snapshot:
            agent.system_prompt = snapshot.get("system_prompt") or ""
        elif snapshot.get("behavior_spec") is not None:
            agent.behavior_spec = canonicalize_behavior_spec(agent.behavior_spec)
            agent.system_prompt = assemble_canonical_system_instructions(
                agent.name, agent.description, agent.behavior_spec
            )
        if "provider_model_id" in snapshot:
            agent.provider_model_id = _uuid_or_none(snapshot.get("provider_model_id"))
        if "provider_credential_id" in snapshot:
            agent.provider_credential_id = _uuid_or_none(
                snapshot.get("provider_credential_id")
            )
        if "provider" in snapshot and snapshot.get("provider") is not None:
            provider = snapshot.get("provider")
            agent.provider = Provider(provider) if isinstance(provider, str) else provider
        if "model" in snapshot:
            agent.model = snapshot.get("model") or ""
        if "fallback_provider_model_id" in snapshot:
            agent.fallback_provider_model_id = _uuid_or_none(
                snapshot.get("fallback_provider_model_id")
            )
        if "fallback_credential_id" in snapshot:
            agent.fallback_credential_id = _uuid_or_none(
                snapshot.get("fallback_credential_id")
            )
        if "fallback_provider" in snapshot:
            fallback_provider = snapshot.get("fallback_provider")
            agent.fallback_provider = (
                Provider(fallback_provider)
                if isinstance(fallback_provider, str) and fallback_provider
                else fallback_provider
            )
        if "fallback_model" in snapshot:
            agent.fallback_model = snapshot.get("fallback_model")
        if "temperature" in snapshot:
            agent.temperature = snapshot.get("temperature")
        if "max_output_tokens" in snapshot:
            agent.max_output_tokens = snapshot.get("max_output_tokens")
        if "session_mode" in snapshot and snapshot.get("session_mode") is not None:
            session_mode = snapshot.get("session_mode")
            agent.session_mode = (
                SessionMode(session_mode) if isinstance(session_mode, str) else session_mode
            )

        settings = deepcopy(agent.settings or {})
        if "response_format" in snapshot:
            response_format = deepcopy(snapshot.get("response_format"))
            if response_format is None:
                settings.pop("response_format", None)
            else:
                settings["response_format"] = response_format
        if "external_context_contract" in snapshot:
            external_context_contract = deepcopy(
                snapshot.get("external_context_contract")
            )
            if external_context_contract is None:
                settings.pop("external_context_contract", None)
            else:
                settings["external_context_contract"] = external_context_contract
        if "runtime_config" in snapshot:
            settings["runtime_config"] = deepcopy(snapshot.get("runtime_config") or {})
        if "knowledge_version_id" in snapshot:
            knowledge_version_id = snapshot.get("knowledge_version_id")
            if knowledge_version_id:
                settings["knowledge_version_id"] = str(knowledge_version_id)
            else:
                settings.pop("knowledge_version_id", None)
        agent.settings = settings
        return agent
