from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput, SourceInfo
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.tool_converter import (
    agent_tools_to_openai_definitions_and_mapping,
)
from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionRequestedV1,
    AgentExecutionStartedV1,
    AgentExecutionToolCompletedV1,
    AgentFallbackTriggeredV1,
)
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase

logger = logging.getLogger(__name__)


class ExplicitRuntimePersistenceMixin:
    """Persistence phases executed as explicit short-lived transactions."""

    async def _prepare(self, input_dto: AskInput):
        async def prepare_database(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ):
            trace_id = uuid4()

            credential_repo = repositories.provider_credentials
            session_repo = repositories.sessions
            message_repo = repositories.messages

            agent = await self._load_agent(repositories, input_dto)
            credential = await self._load_credential(credential_repo, agent)
            api_key = self._decrypt_api_key(credential)
            base_url = self._resolve_base_url(agent, credential)

            response_format = self._get_response_format(agent)
            json_enabled = (
                response_format.get("enabled", False)
                and response_format.get("type") == "json"
            )

            agent_tools: list[dict] = []
            tool_name_to_id: dict[str, str] = {}
            has_tools = False
            try:
                tools = await repositories.tools.list_by_agent(
                    agent.id,
                    status="active",
                )
                if tools:
                    agent_tools, tool_name_to_id = (
                        agent_tools_to_openai_definitions_and_mapping(tools)
                    )
                    has_tools = bool(agent_tools)
            except Exception as exc:
                logger.warning("Failed to load tools for agent %s: %s", agent.id, exc)

            session = await self._resolve_session(session_repo, input_dto, agent)
            history = (
                await self._load_history(message_repo, session)
                if session
                else []
            )

            if session:
                await self._save_user_message(
                    session_repo,
                    message_repo,
                    session,
                    input_dto.message,
                    agent,
                )

            execution_payload: dict[str, Any] = {
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id) if session else None,
                "model": agent.model,
                "provider": (
                    agent.provider.value
                    if hasattr(agent.provider, "value")
                    else agent.provider
                ),
                "message_preview": input_dto.message[:200],
                "has_tools": has_tools,
            }
            requested_event = AgentExecutionRequestedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload=execution_payload,
            )
            await outbox.write(requested_event)

            started_event = AgentExecutionStartedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload={"trace_id": str(trace_id), "model": agent.model},
                correlation_id=requested_event.correlation_id,
                causation_id=requested_event.event_id,
            )
            await outbox.write(started_event)

            return (
                agent,
                session,
                trace_id,
                api_key,
                base_url,
                response_format,
                json_enabled,
                agent_tools,
                tool_name_to_id,
                has_tools,
                history,
            )

        (
            agent,
            session,
            trace_id,
            api_key,
            base_url,
            response_format,
            json_enabled,
            agent_tools,
            tool_name_to_id,
            has_tools,
            history,
        ) = await self._transactions.run(prepare_database)

        # RAG may cross an embedding-provider network boundary. It runs only after
        # the admission transaction has committed and owns its own short DB phases.
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
            agent_tools,
            tool_name_to_id,
            has_tools,
            sources,
            messages,
            history,
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
    ) -> AskOutput:
        async def finalize(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> AskOutput:
            message_id = None
            if session:
                assistant_msg = await self._do_save_assistant_message(
                    repositories.messages,
                    repositories.sessions,
                    outbox,
                    session,
                    answer,
                    usage,
                    agent,
                    tool_calls=tool_calls_recorded,
                )
                message_id = assistant_msg.id

            llm_completed_event = AgentExecutionLLMCompletedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload={
                    "trace_id": str(trace_id),
                    "latency_ms": llm_latency_ms,
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "total_tokens": usage.total_tokens or 0,
                    "cost_usd": usage.cost_usd or 0.0,
                    "model": response_model or agent.model,
                },
            )
            await outbox.write(llm_completed_event)

            for tool_call in tool_calls_recorded or []:
                await outbox.write(
                    AgentExecutionToolCompletedV1.create(
                        agent_id=agent.id,
                        session_id=session.id if session else None,
                        payload={
                            "trace_id": str(trace_id),
                            "tool_name": tool_call.tool_name,
                            "duration_ms": tool_call.duration_ms,
                            "success": tool_call.success,
                            "error": tool_call.error,
                        },
                    )
                )

            completion_payload: dict[str, Any] = {
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id) if session else None,
                "message_id": str(message_id) if message_id else None,
                "answer_length": len(answer),
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
                "total_tokens": usage.total_tokens or 0,
                "cost_usd": usage.cost_usd or 0.0,
                "model": response_model or agent.model,
                "provider": response_provider or "",
                "latency_ms": llm_latency_ms,
                "fallback_used": fallback_used,
                "sources": [item.model_dump() for item in sources]
                if sources
                else None,
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "tool_calls": [
                    item.model_dump() for item in tool_calls_recorded
                ]
                if tool_calls_recorded
                else [],
            }
            if fallback_info_result:
                completion_payload["fallback_info"] = fallback_info_result
                await outbox.write(
                    AgentFallbackTriggeredV1.create(
                        agent_id=agent.id,
                        session_id=session.id if session else None,
                        payload=fallback_info_result,
                    )
                )

            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=completion_payload,
                )
            )

            return AskOutput(
                answer=answer,
                session_id=session.id if session else None,
                message_id=message_id,
                usage=usage,
                sources=sources,
                tool_calls=tool_calls_recorded,
                trace_id=trace_id,
                model=response_model,
                provider=response_provider,
                fallback_used=fallback_used,
                fallback_info=fallback_info_result,
                latency_ms=llm_latency_ms or 0,
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
            )

        return await self._transactions.run(finalize)

    async def _try_fallback(
        self,
        agent,
        messages,
        json_enabled: bool,
        primary_error: str,
    ):
        fallback_provider = (
            agent.fallback_provider.value
            if hasattr(agent.fallback_provider, "value")
            else agent.fallback_provider
        )

        fallback_api_key: str | None = None
        fallback_base_url: str | None = None
        if agent.fallback_credential_id:
            async def load_credential(
                repositories: AgentRuntimeRepositories,
                _outbox: OutboxEventWriter,
            ):
                return await repositories.provider_credentials.get_by_id(
                    agent.fallback_credential_id
                )

            try:
                credential = await self._transactions.run(load_credential)
                if credential:
                    fallback_api_key = self._decrypt_api_key(credential)
                    fallback_base_url = self._resolve_base_url_for_provider(
                        fallback_provider,
                        credential,
                        agent.settings,
                    )
            except Exception as exc:
                logger.warning("Failed to load fallback credential: %s", exc)

        fallback_chat_model = self._llm_factory.create_chat_model(
            provider=fallback_provider,
            model=agent.fallback_model,
            api_key=fallback_api_key or "",
            base_url=fallback_base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if json_enabled else None,
        )

        started = time.monotonic()
        fallback_result = await fallback_chat_model.ainvoke(messages)
        fallback_latency = round((time.monotonic() - started) * 1000)
        fallback_info = {
            "primary_model": agent.model,
            "primary_provider": (
                agent.provider.value
                if hasattr(agent.provider, "value")
                else agent.provider
            ),
            "primary_error": primary_error,
            "fallback_model": agent.fallback_model,
            "fallback_provider": fallback_provider,
            "fallback_credential_id": str(agent.fallback_credential_id),
        }
        return (
            fallback_result,
            fallback_provider,
            fallback_latency,
            fallback_info,
        )


class TransactionalAskAgentUseCase(ExplicitRuntimePersistenceMixin, AskAgentUseCase):
    """Base Agent runtime with explicit transactional repository composition."""

    async def _load_rag_context(
        self,
        agent,
        query: str,
        transactions,
    ) -> tuple[str | None, list[SourceInfo]]:
        async def load(repositories: AgentRuntimeRepositories, _outbox):
            try:
                collections = await repositories.agent_collections.list_by_agent(agent.id)
                if not collections:
                    return None, []

                all_sources: list[SourceInfo] = []
                all_chunks: list[str] = []
                for link in collections:
                    try:
                        results = await repositories.document_chunks.search_similar(
                            embedding=[0.0] * 1536,
                            collection_id=link.collection_id,
                            limit=3,
                            threshold=0.0,
                        )
                    except Exception:
                        continue

                    for chunk, score in results:
                        all_chunks.append(
                            f"[{len(all_sources) + 1}] {chunk.content[:500]}"
                        )
                        all_sources.append(
                            SourceInfo(
                                document_id=(
                                    str(chunk.document_id)
                                    if chunk.document_id
                                    else None
                                ),
                                chunk_id=str(chunk.id),
                                page_number=chunk.page_number,
                                score=round(score, 4),
                                content_preview=chunk.content[:200],
                            )
                        )

                return (
                    ("\n\n".join(all_chunks), all_sources)
                    if all_chunks
                    else (None, [])
                )
            except Exception:
                return None, []

        return await transactions.run(load)
