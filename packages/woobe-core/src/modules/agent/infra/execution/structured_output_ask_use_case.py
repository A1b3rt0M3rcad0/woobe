from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    normalize_contract_for_prompt,
    validate_output_against_contract,
)
from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.events import AgentExecutionFailedV1, AgentMessageCreatedV1
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage
from modules.agent.infra.execution.explicit_runtime_persistence import (
    ExplicitRuntimePersistenceMixin,
)
from modules.agent.infra.execution.instrumented_execution_finalizer import (
    finalize_instrumented_execution,
)
from modules.agent.infra.execution.instrumented_failed_finalizer import (
    finalize_failed_instrumented_execution,
)
from modules.agent.infra.execution.instrumented_fallback_mixin import InstrumentedFallbackMixin
from modules.agent.infra.execution.instrumented_primary_mixin import InstrumentedPrimaryExecutionMixin
from modules.agent.infra.execution.session_continuity_runtime_resolver import (
    SessionContinuityReleaseRuntimeResolver,
)
from shared.contracts.time import utc_now
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


_OUTPUT_CONTRACT_RUNTIME_RULES = (
    "Output contract runtime rules:\n"
    "- Strings such as 'string', 'number', 'float', 'integer', 'boolean', "
    "'object' and 'array' are type declarations in the contract, not literal "
    "values to return.\n"
    "- For 'number' or 'float' fields, return a JSON number such as 0.87, "
    "never the string \"number\" or \"float\".\n"
    "- For 'integer' fields, return an integer. For 'boolean' fields, return "
    "true or false.\n"
    "- Return only the final JSON object."
)

_TOOL_GROUNDING_RUNTIME_RULES = (
    "Tool grounding rules:\n"
    "- The Tool definitions attached to this Model Invocation are the complete "
    "set of runtime Tools available to this Agent. Do not call another Tool just "
    "to discover which Tools exist.\n"
    "- Never invent identifiers, owners, repository names, URLs, resource IDs, "
    "tenant IDs, slugs or keys required by a Tool.\n"
    "- If a qualified identifier is missing, use a real discovery or search Tool "
    "when one is explicitly present in the attached Tool definitions.\n"
    "- If no discovery Tool is available, ask the user for the missing identifier.\n"
    "- Do not try guessed candidates or fabricated alternatives after a Tool rejects "
    "an identifier or reports that a resource was not found."
)


def _id_text(value) -> str | None:
    return str(value) if value else None


def _provider_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


class StructuredOutputAskAgentUseCase(
    InstrumentedFallbackMixin,
    InstrumentedPrimaryExecutionMixin,
    ExplicitRuntimePersistenceMixin,
    SessionContinuityReleaseRuntimeResolver,
):
    """Agent execution with complete LLM and Tool telemetry."""

    def _resolve_base_url_for_provider(self, provider_val, credential, settings):
        """Resolve OpenAI-compatible custom gateways without legacy model metadata."""
        if provider_val == "custom":
            base_url = (
                (settings or {}).get("base_url")
                or (credential.metadata or {}).get("base_url")
            )
            if not base_url:
                from shared.contracts.errors import ValidationError

                raise ValidationError(
                    "Custom provider requires base_url in credential metadata or agent settings"
                )
            return base_url
        return super()._resolve_base_url_for_provider(provider_val, credential, settings)

    def _build_messages(
        self,
        agent,
        rag_context,
        history,
        user_message,
        response_format=None,
    ):
        normalized_response_format = response_format
        if response_format:
            normalized_response_format = dict(response_format)
            normalized_response_format["schema"] = normalize_contract_for_prompt(
                response_format.get("schema")
            )

        messages = super()._build_messages(
            agent,
            rag_context,
            history,
            user_message,
            normalized_response_format,
        )
        if normalized_response_format:
            insert_at = len(messages) - 1 if messages else 0
            messages.insert(
                insert_at,
                SystemMessage(content=_OUTPUT_CONTRACT_RUNTIME_RULES),
            )
        return messages

    async def _prepare(self, input_dto):
        # Runtime Tool selection already resolves the exact Tool set/snapshots in
        # ReleaseRuntimeResolver._prepare(). Agent Runs must not perform MCP discovery
        # or refresh remote Tool catalogs before every model invocation.
        prepared = await super()._prepare(input_dto)
        updated = list(prepared)
        context = current_execution.get()

        if context is not None:
            raw_sources = updated[10] if len(updated) > 10 else []
            context.context_rag_sources = [
                source.model_dump() if hasattr(source, "model_dump") else dict(source)
                for source in raw_sources or []
                if hasattr(source, "model_dump") or isinstance(source, dict)
            ]

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

    async def _save_user_message(
        self,
        session_repo,
        message_repo,
        session,
        content,
        agent,
    ):
        created = await super()._save_user_message(
            session_repo,
            message_repo,
            session,
            content,
            agent,
        )
        context = current_execution.get()
        if context is not None:
            context.input_message_id = created.id
        return created

    async def _do_save_assistant_message(
        self,
        message_repo,
        session_repo,
        outbox,
        session,
        content,
        usage,
        agent,
        tool_calls=None,
        *,
        message_id: UUID | None = None,
        data_extra: dict[str, Any] | None = None,
    ):
        context = current_execution.get()
        sources = context.persisted_sources if context else None
        data: dict[str, Any] = {}
        if tool_calls:
            data["tool_calls"] = [tool.model_dump() for tool in tool_calls]
        if sources:
            data["sources"] = [
                source.model_dump() if hasattr(source, "model_dump") else source
                for source in sources
            ]
        if context is not None and context.run_id is not None:
            data["run_id"] = str(context.run_id)
        data.update(data_extra or {})
        message = Message(
            id=message_id or uuid4(),
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=content,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cost_usd=getattr(usage, "cost_usd", None),
            data=data or None,
        )
        created = await message_repo.create(message)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to update session after saving assistant message: %s",
                exc,
            )

        await outbox.write(
            AgentMessageCreatedV1.create(
                message_id=created.id,
                session_id=session.id,
                project_id=session.project_id,
                agent_id=session.agent_id,
                role="assistant",
            )
        )
        return created

    async def _fail(self, trace_id, agent, session, error, input_dto) -> None:
        context = current_execution.get()
        persistence = getattr(self, "_run_persistence", None)
        if (
            context is not None
            and context.storage_version == EVENT_JOURNAL_STORAGE_VERSION
            and not getattr(context, "defer_persistence", False)
            and context.execution is not None
            and persistence is not None
        ):
            await persistence.fail(
                self,
                session=session,
                agent=agent,
                input_dto=input_dto,
                trace_id=trace_id,
                error=error,
                execution=context.execution,
                started_at=context.started_at,
                prepare_latency_ms=context.prepare_latency_ms,
            )
            return

        if context and context.execution and context.execution.llm_calls:
            try:
                await finalize_failed_instrumented_execution(
                    self,
                    session=session,
                    agent=agent,
                    input_dto=input_dto,
                    trace_id=trace_id,
                    error=error,
                    execution=context.execution,
                    started_at=context.started_at,
                    prepare_latency_ms=context.prepare_latency_ms,
                )
                return
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to emit failed execution telemetry, falling back to minimal failure event: %s",
                    exc,
                )

        provider = _provider_value(getattr(agent, "provider", None))
        fallback_provider = _provider_value(
            getattr(agent, "fallback_provider", None)
        )
        failed_event = AgentExecutionFailedV1.create(
            agent_id=agent.id,
            session_id=session.id if session else (trace_id or agent.id),
            payload={
                "trace_id": str(trace_id) if trace_id else None,
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id) if session else None,
                "provider": provider,
                "model": getattr(agent, "model", None),
                "provider_model_id": _id_text(
                    getattr(agent, "provider_model_id", None)
                ),
                "provider_credential_id": _id_text(
                    getattr(agent, "provider_credential_id", None)
                ),
                "fallback_provider": fallback_provider,
                "fallback_model": getattr(agent, "fallback_model", None),
                "fallback_provider_model_id": _id_text(
                    getattr(agent, "fallback_provider_model_id", None)
                ),
                "fallback_credential_id": _id_text(
                    getattr(agent, "fallback_credential_id", None)
                ),
                "model_binding": {
                    "provider_model_id": _id_text(
                        getattr(agent, "provider_model_id", None)
                    ),
                    "provider_credential_id": _id_text(
                        getattr(agent, "provider_credential_id", None)
                    ),
                    "provider": provider,
                    "model": getattr(agent, "model", None),
                },
                "fallback_model_binding": {
                    "provider_model_id": _id_text(
                        getattr(agent, "fallback_provider_model_id", None)
                    ),
                    "provider_credential_id": _id_text(
                        getattr(agent, "fallback_credential_id", None)
                    ),
                    "provider": fallback_provider,
                    "model": getattr(agent, "fallback_model", None),
                },
                "execution_context": (
                    context.execution_context
                    if context
                    else input_dto.execution_context
                ),
                "agent_release_id": _id_text(
                    context.agent_release_id if context else None
                ),
                "agent_release_version": (
                    context.agent_release_version if context else None
                ),
                "error": error,
            },
        )

        async def persist_failure(
            _repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> None:
            await outbox.write(failed_event)

        try:
            await self._transactions.run(persist_failure)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to emit instrumented AgentExecutionFailedV1: %s",
                exc,
            )

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
                output_parse_error = (
                    output_parse_error
                    or "Output validation failed: "
                    + format_contract_errors(validation_errors)
                )
        if context and context.strict_json and output_parse_error:
            raise ValueError(f"Strict JSON output failed: {output_parse_error}")
        if not context or not context.execution:
            return await super()._finalize(
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
        aggregate, complete, cost_status = aggregate_usage(context.execution.llm_calls)
        persistence = getattr(self, "_run_persistence", None)
        if (
            context.storage_version == EVENT_JOURNAL_STORAGE_VERSION
            and not getattr(context, "defer_persistence", False)
            and persistence is not None
        ):
            return await persistence.complete(
                self,
                session=session,
                agent=agent,
                input_dto=input_dto,
                trace_id=trace_id,
                answer=answer,
                usage=aggregate,
                response_model=response_model,
                response_provider=response_provider,
                sources=sources or [],
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
                execution=context.execution,
                fallback_used=fallback_used,
                fallback_info=fallback_info_result,
                started_at=context.started_at,
                prepare_latency_ms=context.prepare_latency_ms,
                usage_complete=complete,
                cost_status=cost_status,
            )
        return await finalize_instrumented_execution(
            self,
            session=session,
            agent=agent,
            input_dto=input_dto,
            trace_id=trace_id,
            answer=answer,
            usage=aggregate,
            response_model=response_model,
            response_provider=response_provider,
            sources=sources or [],
            parsed_output=parsed_output,
            output_parse_error=output_parse_error,
            execution=context.execution,
            fallback_used=fallback_used,
            fallback_info=fallback_info_result,
            started_at=context.started_at,
            prepare_latency_ms=context.prepare_latency_ms,
            usage_complete=complete,
            cost_status=cost_status,
        )
