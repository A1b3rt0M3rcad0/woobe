from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import uuid6
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import (
    tool_from_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    validate_output_against_contract,
)
from modules.agent.domain.entities import Session
from modules.agent.infra.execution.explicit_runtime_persistence import ExplicitRuntimePersistenceMixin
from modules.agent.infra.execution.runtime_preparation import prepare_rag_binding, prepare_tool_state
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
    _TOOL_GROUNDING_RUNTIME_RULES,
)
from modules.agent.infra.execution.transaction_bounded_rag import (
    TransactionBoundedVectorSnapshotRAGMixin,
    _rag_history_context,
)
from shared.infra.crypto import decrypt_secret
from shared.runtime_environment import normalize_runtime_environment


_NETWORK_INVOCATION_PREFIX = "invocation:"


def _network_hot_session_history(
    state: dict[str, Any],
    *,
    session_id: UUID,
) -> list[Any] | None:
    """Rebuild deferred Agent history from completed Network invocations in Redis."""

    session_text = str(session_id)
    completed: list[dict[str, Any]] = []
    for key, raw in state.items():
        if not key.startswith(_NETWORK_INVOCATION_PREFIX) or not isinstance(raw, dict):
            continue
        if str(raw.get("agent_session_id") or "") != session_text:
            continue
        if raw.get("status") != "completed":
            continue
        completed.append(dict(raw))

    if not completed:
        return None

    # Network invocation ids are UUIDv7, so lexical UUID order preserves creation
    # order for invocations created by the runtime.
    completed.sort(key=lambda item: str(item.get("id") or ""))
    history: list[Any] = []
    for item in completed:
        input_message = item.get("input_message")
        if isinstance(input_message, str) and input_message:
            history.append(HumanMessage(content=input_message))

        raw_tool_calls = item.get("tool_calls")
        tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []
        model_tool_calls = [
            {
                "id": str(call["tool_call_id"]),
                "name": str(call["tool_name"]),
                "args": call.get("input") or {},
            }
            for call in tool_calls
            if isinstance(call, dict)
            and call.get("tool_call_id")
            and call.get("tool_name")
        ]

        output_message = item.get("output_message")
        if output_message is not None:
            content = str(output_message)
            history.append(
                AIMessage(content=content, tool_calls=model_tool_calls)
                if model_tool_calls
                else AIMessage(content=content)
            )

        for call in tool_calls:
            if (
                not isinstance(call, dict)
                or not call.get("tool_call_id")
                or call.get("output") is None
            ):
                continue
            history.append(
                ToolMessage(
                    content=json.dumps(
                        call["output"],
                        ensure_ascii=False,
                        default=str,
                    ),
                    tool_call_id=str(call["tool_call_id"]),
                )
            )

    return history


class TransactionBoundedStructuredOutputRuntime(
    TransactionBoundedVectorSnapshotRAGMixin,
    StructuredOutputAskAgentUseCase,
):
    """Runtime shared by standalone and Network-deferred Agent executions."""

    @staticmethod
    def _defer_persistence(input_dto: Any) -> bool:
        metadata = getattr(input_dto, "metadata", None)
        return bool(
            isinstance(metadata, dict)
            and metadata.get("source") == "network_runtime"
            and metadata.get("defer_persistence") is True
        )

    async def _prepare_deferred_network(self, input_dto):
        async def read_prepare(repositories, _outbox):
            agent = await self._load_agent(repositories, input_dto)
            credential = await self._load_credential(repositories.provider_credentials, agent)
            fallback_credential = None
            if agent.fallback_credential_id:
                fallback_credential = await repositories.provider_credentials.get_by_id(
                    agent.fallback_credential_id
                )
            tools, encrypted_tool_secrets = await prepare_tool_state(
                repositories,
                agent=agent,
                tool_from_snapshot=tool_from_release_snapshot,
                tool_with_permissions=tool_with_permission_overrides,
            )
            rag_binding = await prepare_rag_binding(repositories, agent=agent)
            session = None
            existing_session = False
            session_missing = False
            if input_dto.session_id is not None:
                session = await repositories.sessions.get_by_id(input_dto.session_id)
                if session is None:
                    # A stateful Agent Session created earlier in this same Network
                    # Run is intentionally not durable until Network Finalization.
                    session_missing = True
                else:
                    if (
                        session.project_id != input_dto.project_id
                        or session.agent_id != agent.id
                    ):
                        raise ValueError(
                            "Pinned Agent Session does not belong to this Agent"
                        )
                    existing_session = True
            elif str(getattr(agent.session_mode, "value", agent.session_mode)) == "stateful":
                session = Session(
                    id=uuid6.uuid7(),
                    project_id=input_dto.project_id,
                    agent_id=agent.id,
                    runtime_environment=normalize_runtime_environment(input_dto.execution_context),
                    opened_release_id=input_dto.loaded_release_id,
                    tenant_id=input_dto.tenant_id,
                    user_id=input_dto.user_id,
                )
            history = (
                await self._load_history(repositories.messages, session)
                if session is not None and existing_session
                else []
            )
            response_format = self._get_response_format(agent)
            json_enabled = (
                response_format.get("enabled", False)
                and response_format.get("type") == "json"
            )
            definitions, name_to_id = (
                agent_tools_to_openai_definitions_and_mapping(tools)
                if tools
                else ([], {})
            )
            return (
                agent,
                session,
                credential,
                fallback_credential,
                tools,
                encrypted_tool_secrets,
                rag_binding,
                history,
                response_format,
                json_enabled,
                definitions,
                name_to_id,
                session_missing,
            )

        (
            agent,
            session,
            credential,
            fallback_credential,
            tools,
            encrypted_tool_secrets,
            rag_binding,
            history,
            response_format,
            json_enabled,
            definitions,
            name_to_id,
            session_missing,
        ) = await self._transactions.read(read_prepare)

        context = current_execution.get()
        if session_missing:
            if (
                input_dto.session_id is None
                or context is None
                or context.network_execution_id is None
                or self._execution_state_store is None
            ):
                raise ValueError("Pinned Agent Session was not found")

            # Redis is consulted only after the short SQL read scope has ended. A
            # missing SQL Session is valid only when a completed invocation in this
            # same Network Run proves that the session exists in deferred hot state.
            network_state = (
                await self._execution_state_store.get(context.network_execution_id)
                or {}
            )
            hot_history = _network_hot_session_history(
                network_state,
                session_id=input_dto.session_id,
            )
            if hot_history is None:
                raise ValueError("Pinned Agent Session was not found")

            session = Session(
                id=input_dto.session_id,
                project_id=input_dto.project_id,
                agent_id=agent.id,
                runtime_environment=normalize_runtime_environment(
                    input_dto.execution_context
                ),
                opened_release_id=input_dto.loaded_release_id,
                tenant_id=input_dto.tenant_id,
                user_id=input_dto.user_id,
            )
            history = hot_history

        # Every NetworkInvocation causes exactly one AgentRun. Reusing the UUID
        # gives the bulk finalizer a stable identity without a child SQL write.
        run_id = (
            context.network_invocation_id
            if context is not None and context.network_invocation_id is not None
            else uuid6.uuid7()
        )
        trace_id = uuid6.uuid7()
        api_key = self._decrypt_api_key(credential)
        base_url = self._resolve_base_url(agent, credential)
        fallback_data = None
        if fallback_credential is not None:
            fallback_provider = (
                agent.fallback_provider.value
                if hasattr(agent.fallback_provider, "value")
                else agent.fallback_provider
            )
            fallback_data = {
                "api_key": self._decrypt_api_key(fallback_credential),
                "base_url": self._resolve_base_url_for_provider(
                    fallback_provider,
                    fallback_credential,
                    agent.settings,
                ),
            }
        tool_secrets = {
            name: decrypt_secret(value, self._encryption_key)
            for name, value in encrypted_tool_secrets.items()
        }
        if context is not None:
            context.run_id = run_id
            context.trace_id = trace_id
            context.session_id = session.id if session else None
            context.prepared_fallback = fallback_data
            context.prepared_tools = {str(tool.id): tool for tool in tools}
            context.prepared_tool_secrets = tool_secrets
            context.prepared_rag = rag_binding
            setattr(context, "defer_persistence", True)

        if self._execution_state_store is not None:
            await self._execution_state_store.create(
                run_id,
                {
                    "status": "running",
                    "phase": "prepared",
                    "network_deferred": True,
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(agent.id),
                    "session_id": str(session.id) if session else None,
                    "trace_id": str(trace_id),
                    "network_execution_id": (
                        str(context.network_execution_id)
                        if context and context.network_execution_id
                        else None
                    ),
                    "network_invocation_id": (
                        str(context.network_invocation_id)
                        if context and context.network_invocation_id
                        else None
                    ),
                    "input_message": input_dto.message,
                },
                ttl_seconds=self._execution_state_ttl_seconds,
            )

        rag_context, sources = await self._load_rag_context(
            agent,
            input_dto.message,
            self._transactions,
        )
        messages = self._build_messages(
            agent,
            rag_context,
            history,
            input_dto.message,
            response_format if json_enabled else None,
        )
        return (
            agent,
            session,
            trace_id,
            api_key,
            base_url,
            response_format,
            json_enabled,
            definitions,
            name_to_id,
            bool(definitions),
            sources,
            messages,
            history,
        )

    async def _prepare(self, input_dto):
        token = _rag_history_context.set([])
        try:
            if self._defer_persistence(input_dto):
                prepared = await self._prepare_deferred_network(input_dto)
            else:
                prepared = await super(StructuredOutputAskAgentUseCase, self)._prepare(input_dto)
            prepared = await self._apply_runtime_tool_selection(prepared)
            updated = list(prepared)
            context = current_execution.get()

            if context and context.internal_tool_definitions:
                definitions = list(updated[7])
                mapping = dict(updated[8])
                internal_mapping = context.internal_tool_name_to_id or {}
                collisions = set(mapping).intersection(internal_mapping)
                if collisions:
                    raise ValueError(
                        "Network delegation tool name collides with an Agent Tool: "
                        + ", ".join(sorted(collisions))
                    )
                definitions.extend(context.internal_tool_definitions)
                mapping.update(internal_mapping)
                updated[7] = definitions
                updated[8] = mapping
                updated[9] = bool(definitions)

            if updated[9]:
                messages = list(updated[11])
                insert_at = len(messages) - 1 if messages else 0
                messages.insert(
                    insert_at,
                    SystemMessage(content=_TOOL_GROUNDING_RUNTIME_RULES),
                )
                updated[11] = messages
            return tuple(updated)
        finally:
            _rag_history_context.reset(token)

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
        context = current_execution.get()
        if context is not None:
            context.persisted_sources = list(sources or [])
        response_format = self._get_response_format(agent)
        if (
            response_format.get("enabled", False)
            and response_format.get("type") == "json"
            and parsed_output is not None
        ):
            validation_errors = validate_output_against_contract(
                parsed_output,
                response_format.get("schema"),
            )
            if validation_errors:
                output_parse_error = output_parse_error or (
                    "Output validation failed: " + format_contract_errors(validation_errors)
                )
        if context and context.strict_json and output_parse_error:
            raise ValueError(f"Strict JSON output failed: {output_parse_error}")

        if context and getattr(context, "defer_persistence", False):
            result_payload = {
                "answer": answer,
                "usage": (
                    usage.model_dump() if hasattr(usage, "model_dump") else None
                ),
                "sources": [item.model_dump() for item in sources or []],
                "tool_calls": [
                    item.model_dump() for item in tool_calls_recorded or []
                ],
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "provider": response_provider,
                "model": response_model,
                "trace_id": str(trace_id),
                "run_id": str(context.run_id) if context.run_id else None,
                "session_id": str(session.id) if session else None,
                "llm_calls": context.execution.llm_calls if context.execution else [],
            }
            await self._hot_terminal_pending(
                terminal_status="completed",
                result=result_payload,
            )
            return AskOutput(
                run_id=context.run_id,
                answer=answer,
                session_id=session.id if session else None,
                usage=usage,
                sources=sources or [],
                tool_calls=tool_calls_recorded or [],
                trace_id=trace_id,
                model=response_model,
                provider=response_provider,
                provider_model_id=getattr(agent, "provider_model_id", None),
                provider_credential_id=getattr(agent, "provider_credential_id", None),
                fallback_provider_model_id=getattr(
                    agent,
                    "fallback_provider_model_id",
                    None,
                ),
                fallback_credential_id=getattr(agent, "fallback_credential_id", None),
                fallback_used=fallback_used,
                fallback_info=fallback_info_result,
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
            )

        return await StructuredOutputAskAgentUseCase._finalize(
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
        )

    async def _fail(self, trace_id, agent, session, error, input_dto) -> None:
        context = current_execution.get()
        if context and getattr(context, "defer_persistence", False):
            await self._hot_terminal_pending(
                terminal_status="failed",
                result={
                    "error": error,
                    "run_id": str(context.run_id) if context.run_id else None,
                    "trace_id": str(trace_id) if trace_id else None,
                    "session_id": str(session.id) if session else None,
                },
            )
            return
        if context and context.execution and context.execution.llm_calls:
            return await StructuredOutputAskAgentUseCase._fail(
                self,
                trace_id,
                agent,
                session,
                error,
                input_dto,
            )
        return await ExplicitRuntimePersistenceMixin._fail(
            self,
            trace_id,
            agent,
            session,
            error,
            input_dto,
        )
