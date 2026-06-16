from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from modules.agent.domain.errors import AgentNotFoundError, CredentialNotFoundError

from modules.agent.domain.entities import Agent, AgentRelease, Message, ProviderCredential, Session
from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentExecutionRequestedV1,
    AgentFallbackTriggeredV1,
    AgentMessageCreatedV1,
)
from modules.agent.domain.enums import MessageRole, RuntimeSessionMode as SessionMode
from modules.agent.domain.repositories import (
    AgentCollectionRepository,
    AgentReleaseRepository,
    AgentRepository,
    DocumentChunkRepository,
    MessageRepository,
    ProviderCredentialRepository,
    SessionRepository,
)
from modules.agent.domain.ports.llm_factory import LLMFactory
from modules.agent.domain.ports.tool_executor import ToolExecutor
from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
    SourceInfo,
    ToolCallInfo,
    UsageInfo,
)
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions, _safe_tool_name
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAgentReleaseRepository,
)
from modules.agent.infra.adapters.tool_executor import AgentToolExecutor
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret

logger = logging.getLogger(__name__)


class AskAgentStreamService:

    def __init__(
        self,
        session_factory: Callable[..., Any],
        llm_factory: LLMFactory,
    ) -> None:
        self._session_factory = session_factory
        self._llm_factory = llm_factory
        self._encryption_key = Settings().encryption_key

    async def generate(self, input_dto: AskInput) -> AsyncGenerator[str, None]:
        started_at = time.monotonic()
        trace_id: UUID | None = None
        session: Session | None = None
        agent: Agent | None = None
        response_model: str | None = None
        response_provider: str | None = None
        usage_info: UsageInfo | None = None
        full_answer: str | None = None

        try:
            async with AgentUnitOfWork(self._session_factory) as uow:
                agent = await self._load_agent(uow.agents, SQLAlchemyAgentReleaseRepository(uow), input_dto)
                credential = await self._load_credential(uow.provider_credentials, agent)
                api_key = self._decrypt_api_key(credential)
                base_url = self._resolve_base_url(agent, credential)

                response_format = self._get_response_format(agent)
                json_enabled = (
                    response_format.get("enabled", False)
                    and response_format.get("type") == "json"
                )

                session = await self._resolve_session(uow.sessions, input_dto, agent)

                history: list = []
                if session:
                    history = await self._load_history(uow.messages, session)

                if session:
                    await self._save_user_message(uow.sessions, uow.messages, session, input_dto.message, agent)

                trace_id = uuid4()
                rag_context, sources = await self._load_rag_context(
                    uow.document_collections, uow.document_chunks, agent, input_dto.message,
                )

                messages = self._build_messages(agent, rag_context, history, input_dto.message, response_format if json_enabled else None)

                outbox = SQLAlchemyAgentOutboxEventWriter(uow)
                execution_payload: dict[str, Any] = {
                    "trace_id": str(trace_id),
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(agent.id),
                    "session_id": str(session.id) if session else None,
                    "model": agent.model,
                    "provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                    "message_preview": input_dto.message[:200],
                }
                requested_event = AgentExecutionRequestedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=execution_payload,
                )
                outbox.write(requested_event)

                if sources:
                    yield self._sse_event("sources", {"sources": [s.model_dump() for s in sources]})

                yield self._sse_event("meta", {
                    "session_id": str(session.id) if session else None,
                    "trace_id": str(trace_id) if trace_id else None,
                })

            agent_tools: list[dict] = []
            tool_executor: ToolExecutor | None = None
            tool_name_to_id: dict[str, str] = {}
            has_tools = False
            try:
                async with AgentUnitOfWork(self._session_factory) as tool_uow:
                    tool_repo = tool_uow.tools
                    tools = await tool_repo.list_by_agent(agent.id, status="active")
                    if tools:
                        agent_tools = agent_tools_to_openai_definitions(tools)
                        tool_executor = AgentToolExecutor(tool_repo)
                        for t in tools:
                            tool_name_to_id[_safe_tool_name(t)] = str(t.id)
                        has_tools = True
            except Exception as e:
                logger.warning("Failed to load tools for agent %s: %s", agent.id, e)

            chat_model = self._llm_factory.create_chat_model(
                provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                model=agent.model,
                api_key=api_key,
                base_url=base_url,
                temperature=agent.temperature or 0.2,
                max_tokens=agent.max_output_tokens or 1000,
                streaming=True,
                response_format={"type": "json_object"} if (json_enabled and not has_tools) else None,
            )

            if has_tools:
                chat_model = chat_model.bind_tools(agent_tools, tool_choice="auto")

            fallback_used = False
            fallback_info_result: dict | None = None
            fallback_provider_val: str | None = None
            accumulated: list[str] = []
            input_tokens: int | None = None
            output_tokens: int | None = None
            total_tokens: int | None = None

            tool_calls_recorded: list[ToolCallInfo] = []
            tool_was_called = False
            aggregated_message = None

            async def _run_stream(chat_model_instance):
                nonlocal accumulated, input_tokens, output_tokens, total_tokens, aggregated_message
                local_accumulated: list[str] = []
                local_input_tokens: int | None = None
                local_output_tokens: int | None = None
                local_total_tokens: int | None = None
                local_aggregated = None
                logger.info("SENDING TO LLM: %d messages", len(messages))
                for i, msg in enumerate(messages):
                    role = type(msg).__name__
                    content_preview = (getattr(msg, "content", "") or "")[:100]
                    logger.info("  MSG[%d] %s: %s", i, role, content_preview)
                async for chunk in chat_model_instance.astream(messages):
                    content = chunk.content if hasattr(chunk, "content") and chunk.content else ""
                    if content:
                        local_accumulated.append(content)
                        yield self._sse_event("token", {"content": content})
                    usage_meta = getattr(chunk, "usage_metadata", None)
                    if usage_meta is not None and usage_meta:
                        if usage_meta.get("input_tokens") is not None:
                            local_input_tokens = usage_meta["input_tokens"]
                        if usage_meta.get("output_tokens") is not None:
                            local_output_tokens = usage_meta["output_tokens"]
                        if usage_meta.get("total_tokens") is not None:
                            local_total_tokens = usage_meta["total_tokens"]
                    if local_aggregated is None:
                        local_aggregated = chunk
                    else:
                        local_aggregated = local_aggregated + chunk
                accumulated = local_accumulated
                input_tokens = local_input_tokens
                output_tokens = local_output_tokens
                total_tokens = local_total_tokens
                aggregated_message = local_aggregated

            def _has_tool_calls(msg) -> bool:
                return bool(getattr(msg, "tool_calls", None))

            llm_latency_start = time.monotonic()
            try:
                async for event in _run_stream(chat_model):
                    yield event
                llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)

                tool_call_rounds = 0
                while aggregated_message and _has_tool_calls(aggregated_message) and tool_call_rounds < 5:
                    tool_was_called = True
                    messages.append(aggregated_message)
                    for tc in (getattr(aggregated_message, "tool_calls", None) or []):
                        tool_start = time.monotonic()
                        resolved_tool_id = tool_name_to_id.get(tc["name"], tc["name"])
                        tool_output = {"success": False, "error": "Tool execution not available"}
                        if tool_executor:
                            try:
                                tool_args = tc.get("args", {}) or {}
                                tool_output = await tool_executor.execute_tool(
                                    UUID(resolved_tool_id), tool_args,
                                )
                            except Exception as tool_e:
                                logger.warning("Tool execution failed: %s", tool_e)
                                tool_output = {"success": False, "error": str(tool_e)}
                        tool_duration = round((time.monotonic() - tool_start) * 1000)
                        tool_success = tool_output.get("success", False)
                        tool_error = tool_output.get("error")
                        tool_calls_recorded.append(ToolCallInfo(
                            tool_call_id=tc["id"],
                            tool_name=tc["name"],
                            input=tc.get("args"),
                            output=tool_output,
                            duration_ms=tool_duration,
                            success=tool_success,
                            error=tool_error,
                        ))
                        yield self._sse_event("tool_call", {
                            "tool_name": tc["name"],
                            "input": tc.get("args"),
                            "output": tool_output,
                            "duration_ms": tool_duration,
                            "success": tool_success,
                            "error": tool_error,
                        })
                        messages.append(ToolMessage(
                            content=json.dumps(tool_output) if isinstance(tool_output, dict) else str(tool_output),
                            tool_call_id=tc["id"],
                        ))

                    tool_call_rounds += 1
                    aggregated_message = None
                    accumulated = []
                    input_tokens = None
                    output_tokens = None
                    total_tokens = None

                    try:
                        async for event in _run_stream(chat_model):
                            yield event
                        llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)
                    except Exception as tool_stream_e:
                        logger.warning("Tool call follow-up LLM stream failed: %s", tool_stream_e)
                        break

                if json_enabled and tool_was_called:
                    try:
                        answer_text = "".join(accumulated)
                        schema_json = json.dumps(response_format.get("schema", {}), indent=2)
                        json_model = self._llm_factory.create_chat_model(
                            provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                            model=agent.model,
                            api_key=api_key,
                            base_url=base_url,
                            temperature=0.0,
                            max_tokens=agent.max_output_tokens or 1000,
                            response_format={"type": "json_object"},
                        )
                        json_result = await json_model.ainvoke([
                            SystemMessage(
                                content=(
                                    "Responda APENAS com JSON válido seguindo este schema.\n"
                                    "NÃO inclua markdown, explicações ou texto fora do JSON.\n"
                                    f"<schema>\n{schema_json}\n</schema>"
                                )
                            ),
                            HumanMessage(content=f"Converta a resposta abaixo para JSON válido:\n\n{answer_text}"),
                        ])
                        accumulated = [json_result.content]

                    except Exception as json_e:
                        logger.warning("JSON formatting phase (Fase 2) failed: %s", json_e)

            except Exception as e:
                primary_error = str(e)

                if agent and agent.fallback_model and agent.fallback_credential_id:
                    yield self._sse_event("fallback", {
                        "primary_error": primary_error,
                        "primary_model": agent.model,
                        "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                        "fallback_model": agent.fallback_model,
                        "fallback_provider": agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider,
                    })

                    try:
                        async with AgentUnitOfWork(self._session_factory) as fb_uow:
                            fallback_credential = await self._load_credential_by_id(fb_uow.provider_credentials, agent.fallback_credential_id)
                            fallback_api_key = self._decrypt_api_key(fallback_credential)
                            fb_provider_val = agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider
                            fallback_base_url = self._resolve_base_url_for_provider(fb_provider_val, fallback_credential, agent.settings)

                        fallback_chat_model = self._llm_factory.create_chat_model(
                            provider=fb_provider_val,
                            model=agent.fallback_model,
                            api_key=fallback_api_key,
                            base_url=fallback_base_url,
                            temperature=agent.temperature or 0.2,
                            max_tokens=agent.max_output_tokens or 1000,
                            streaming=True,
                            response_format={"type": "json_object"} if json_enabled else None,
                        )

                        accumulated = []
                        input_tokens = None
                        output_tokens = None
                        total_tokens = None
                        llm_latency_start = time.monotonic()

                        async for event in _run_stream(fallback_chat_model):
                            yield event

                        fallback_used = True
                        fallback_provider_val = fb_provider_val
                        fallback_info_result = {
                            "primary_model": agent.model,
                            "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                            "primary_error": primary_error,
                            "fallback_model": agent.fallback_model,
                            "fallback_provider": fb_provider_val,
                            "fallback_credential_id": str(agent.fallback_credential_id),
                        }
                    except Exception as fb_e:
                        combined_error = f"Primary: {primary_error} | Fallback: {fb_e}"
                        logger.exception("Fallback also failed: %s", fb_e)
                        raise ValueError(combined_error) from fb_e
                else:
                    raise ValueError(f"AI provider error: {primary_error}") from e

            llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)
            full_answer = "".join(accumulated)

            parsed_output = None
            output_parse_error = None
            if json_enabled:
                try:
                    cleaned = self._clean_json_answer(full_answer)
                    parsed_output = json.loads(cleaned)
                except (json.JSONDecodeError, Exception) as e:
                    output_parse_error = str(e)

            if not fallback_used:
                if hasattr(chat_model, "model"):
                    response_model = chat_model.model
                response_provider = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
            else:
                response_model = agent.fallback_model
                response_provider = fallback_provider_val or (agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider)

            logger.info("Stream LLM usage debug", extra={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            })
            usage_info = UsageInfo(
                input_tokens=input_tokens if input_tokens else None,
                output_tokens=output_tokens if output_tokens else None,
                total_tokens=total_tokens if total_tokens else None,
                cost_usd=None,
            )

        except Exception as e:
            logger.exception("Stream error: %s", e)
            yield self._sse_event("error", {"message": str(e)})
            try:
                if agent:
                    async with AgentUnitOfWork(self._session_factory) as fail_uow:
                        fail_outbox = SQLAlchemyAgentOutboxEventWriter(fail_uow)
                        failed_event = AgentExecutionFailedV1.create(
                            agent_id=agent.id,
                            session_id=session.id if session else None,
                            payload={
                                "trace_id": str(trace_id) if trace_id else None,
                                "project_id": str(input_dto.project_id),
                                "agent_id": str(agent.id),
                                "error": str(e),
                            },
                        )
                        fail_outbox.write(failed_event)
            except Exception:
                pass
            return

        try:
            async with AgentUnitOfWork(self._session_factory) as finalize_uow:
                outbox = SQLAlchemyAgentOutboxEventWriter(finalize_uow)

                message_id = None
                if session:
                    assistant_msg = await self._save_assistant_message(
                        finalize_uow.messages, finalize_uow.sessions, outbox, session, full_answer or "", usage_info, agent,
                        tool_calls=tool_calls_recorded,
                        sources=sources,
                        model=response_model or agent.model,
                        provider=response_provider,
                    )
                    message_id = assistant_msg.id

                completion_payload: dict[str, Any] = {
                    "trace_id": str(trace_id),
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(agent.id),
                    "session_id": str(session.id) if session else None,
                    "message_id": str(message_id) if message_id else None,
                    "answer_length": len(full_answer or ""),
                    "input_tokens": usage_info.input_tokens or 0 if usage_info else 0,
                    "output_tokens": usage_info.output_tokens or 0 if usage_info else 0,
                    "total_tokens": usage_info.total_tokens or 0 if usage_info else 0,
                    "cost_usd": usage_info.cost_usd or 0.0 if usage_info else 0.0,
                    "model": response_model or agent.model,
                    "provider": response_provider,
                    "latency_ms": llm_latency_ms,
                    "fallback_used": fallback_used,
                    "sources": [s.model_dump() for s in sources] if sources else [],
                    "tool_calls": [tc.model_dump() for tc in tool_calls_recorded] if tool_calls_recorded else [],
                }
                if fallback_info_result:
                    completion_payload["fallback_info"] = fallback_info_result
                    fallback_event = AgentFallbackTriggeredV1.create(
                        agent_id=agent.id,
                        session_id=session.id if session else None,
                        payload=fallback_info_result,
                    )
                    outbox.write(fallback_event)

                completed_event = AgentExecutionCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=completion_payload,
                )
                outbox.write(completed_event)

                total_latency = round((time.monotonic() - started_at) * 1000)

                done_payload: dict[str, Any] = {
                    "answer": full_answer or "",
                    "session_id": str(session.id) if session else None,
                    "message_id": str(message_id) if message_id else None,
                    "usage": usage_info.model_dump() if usage_info else None,
                    "sources": [s.model_dump() for s in sources] if sources else [],
                    "model": response_model or agent.model,
                    "provider": response_provider,
                    "latency_ms": total_latency,
                    "trace_id": str(trace_id) if trace_id else None,
                    "parsed_output": parsed_output,
                    "output_parse_error": output_parse_error,
                    "fallback_used": fallback_used,
                    "fallback_info": fallback_info_result,
                    "tool_calls": [tc.model_dump() for tc in tool_calls_recorded] if tool_calls_recorded else [],
                }

                yield self._sse_event("done", done_payload)

        except Exception as teardown_e:
            logger.exception("Teardown error: %s", teardown_e)
            yield self._sse_event("error", {"message": f"Teardown error: {teardown_e}"})

    def _sse_event(self, event_type: str, data: dict[str, Any]) -> str:
        payload = {"type": event_type, **data}
        return f"data: {json.dumps(payload, default=str)}\n\n"

    async def _load_agent(
        self, repo: AgentRepository, release_repo: AgentReleaseRepository, input_dto: AskInput
    ) -> Agent:
        agent = await repo.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        if hasattr(agent, "status") and agent.status and hasattr(agent.status, "value") and agent.status.value != "active":
            raise ValueError(f"Agent {input_dto.agent_id} is not active")

        if input_dto.execution_context == "production":
            release = await release_repo.get_active_production(input_dto.agent_id)
            if release is None:
                raise ValueError(f"No production release deployed for agent {input_dto.agent_id}")
            agent = self._apply_release_to_agent(agent, release)
        elif input_dto.loaded_release_id:
            release = await release_repo.get_by_id(input_dto.loaded_release_id)
            if release:
                agent = self._apply_release_to_agent(agent, release)
        elif input_dto.snapshot_override:
            agent = self._apply_snapshot_override(agent, input_dto.snapshot_override)

        return agent

    def _apply_release_to_agent(self, agent: Agent, release: AgentRelease) -> Agent:
        if release.system_prompt is not None:
            agent.system_prompt = release.system_prompt
        if release.response_format is not None:
            settings = dict(agent.settings) if agent.settings else {}
            settings["response_format"] = release.response_format
            agent.settings = settings
        if release.provider is not None:
            from modules.agent.domain.enums import Provider
            agent.provider = Provider(release.provider) if isinstance(release.provider, str) else release.provider
        if release.model is not None:
            agent.model = release.model
        if release.provider_credential_id is not None:
            agent.provider_credential_id = release.provider_credential_id
        if release.fallback_provider is not None:
            from modules.agent.domain.enums import Provider
            agent.fallback_provider = Provider(release.fallback_provider) if isinstance(release.fallback_provider, str) else release.fallback_provider
        if release.fallback_model is not None:
            agent.fallback_model = release.fallback_model
        if release.fallback_credential_id is not None:
            agent.fallback_credential_id = release.fallback_credential_id
        if release.temperature is not None:
            agent.temperature = release.temperature
        if release.max_output_tokens is not None:
            agent.max_output_tokens = release.max_output_tokens
        if release.session_mode is not None:
            from modules.agent.domain.enums import SessionMode
            agent.session_mode = SessionMode(release.session_mode) if isinstance(release.session_mode, str) else release.session_mode
        return agent

    def _apply_snapshot_override(self, agent: Agent, snapshot: dict) -> Agent:
        if snapshot.get("system_prompt") is not None:
            agent.system_prompt = snapshot["system_prompt"]
        if snapshot.get("response_format") is not None:
            settings = dict(agent.settings) if agent.settings else {}
            settings["response_format"] = snapshot["response_format"]
            agent.settings = settings
        if snapshot.get("provider") is not None:
            from modules.agent.domain.enums import Provider
            agent.provider = Provider(snapshot["provider"]) if isinstance(snapshot["provider"], str) else snapshot["provider"]
        if snapshot.get("model") is not None:
            agent.model = snapshot["model"]
        if snapshot.get("provider_credential_id") is not None:
            agent.provider_credential_id = UUID(snapshot["provider_credential_id"]) if isinstance(snapshot["provider_credential_id"], str) else snapshot["provider_credential_id"]
        if snapshot.get("temperature") is not None:
            agent.temperature = snapshot["temperature"]
        if snapshot.get("max_output_tokens") is not None:
            agent.max_output_tokens = snapshot["max_output_tokens"]
        if snapshot.get("session_mode") is not None:
            from modules.agent.domain.enums import SessionMode
            agent.session_mode = SessionMode(snapshot["session_mode"]) if isinstance(snapshot["session_mode"], str) else snapshot["session_mode"]
        if snapshot.get("fallback_provider"):
            from modules.agent.domain.enums import Provider
            agent.fallback_provider = Provider(snapshot["fallback_provider"]) if isinstance(snapshot["fallback_provider"], str) else snapshot["fallback_provider"]
        if snapshot.get("fallback_model"):
            agent.fallback_model = snapshot["fallback_model"]
        if snapshot.get("fallback_credential_id"):
            agent.fallback_credential_id = UUID(snapshot["fallback_credential_id"]) if isinstance(snapshot["fallback_credential_id"], str) else snapshot["fallback_credential_id"]
        return agent

    async def _load_credential_by_id(self, repo: ProviderCredentialRepository, credential_id: UUID) -> ProviderCredential:
        credential = await repo.get_by_id(credential_id)
        if not credential:
            raise CredentialNotFoundError(credential_id)
        return credential

    async def _load_credential(self, repo: ProviderCredentialRepository, agent: Agent) -> ProviderCredential:
        if not agent.provider_credential_id:
            raise ValueError("Agent has no provider credential configured")
        return await self._load_credential_by_id(repo, agent.provider_credential_id)

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", credential.id, e)
            raise ValueError("Provider credential secret could not be decrypted. Recreate the credential.")

    def _resolve_base_url_for_provider(
        self, provider_val: str, credential: ProviderCredential, settings: dict | None
    ) -> str | None:
        if provider_val == "custom":
            base_url = (
                (settings or {}).get("base_url")
                or (credential.metadata or {}).get("base_url")
            )
            if not base_url:
                raise ValueError("Custom provider requires base_url in credential metadata or agent settings")
            model = (settings or {}).get("model") or (credential.metadata or {}).get("model")
            if not model:
                raise ValueError("Custom provider requires model in agent or credential metadata")
            return base_url
        return None

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        provider_val = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        return self._resolve_base_url_for_provider(provider_val, credential, agent.settings)

    async def _resolve_session(
        self, repo: SessionRepository, input_dto: AskInput, agent: Agent
    ) -> Session | None:
        if input_dto.session_id:
            try:
                found = await repo.get_by_id(input_dto.session_id)
                logger.info("RESOLVE SESSION: found existing session %s", found.id)
                return found
            except Exception as exc:
                logger.warning("RESOLVE SESSION: get_by_id failed for %s: %s", input_dto.session_id, exc)

        mode = agent.session_mode.value if hasattr(agent.session_mode, "value") else agent.session_mode
        logger.info("RESOLVE SESSION: agent mode=%s, will create new", mode)
        if mode == "stateless":
            logger.info("RESOLVE SESSION: stateless mode, returning None")
            return None

        session = Session(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            external_session_id=None,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            mode=SessionMode.CHAT,
        )
        created = await repo.create(session)
        logger.info("RESOLVE SESSION: created new session %s", created.id)
        return created

    async def _save_user_message(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        session: Session,
        content: str,
        agent: Agent,
    ) -> Message:
        msg = Message(
            project_id=session.project_id,
            agent_id=agent.id,
            session_id=session.id,
            role=MessageRole.USER,
            content=content,
        )
        created = await message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception:
            pass
        return created

    async def _save_assistant_message(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        outbox: OutboxEventWriter,
        session: Session,
        content: str,
        usage: UsageInfo,
        agent: Agent,
        tool_calls: list[ToolCallInfo] | None = None,
        sources: list[SourceInfo] | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> Message:
        msg = Message(
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            data={
                "tool_calls": [tc.model_dump() for tc in tool_calls] if tool_calls else None,
                "sources": [s.model_dump() for s in sources] if sources else None,
                "model": model,
                "provider": provider,
            } if tool_calls or sources or model or provider else None,
        )
        created = await message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception:
            pass

        event = AgentMessageCreatedV1.create(
            message_id=created.id,
            session_id=session.id,
            project_id=session.project_id,
            agent_id=session.agent_id,
            role="assistant",
            payload=msg.data,
        )
        await outbox.write(event)
        return created

    async def _load_history(self, repo: MessageRepository, session: Session) -> list:
        try:
            messages = await repo.list_by_session(session.id)
            logger.debug("Loaded %d raw messages from DB for session %s", len(messages), session.id)
            history = []
            for m in messages:
                role = m.role.value if hasattr(m.role, "value") else m.role
                if role == "user":
                    history.append(HumanMessage(content=m.content))
                elif role == "assistant":
                    raw_tool_calls = (m.data or {}).get("tool_calls") or []
                    tool_calls = None
                    if raw_tool_calls:
                        tool_calls = [
                            {"id": tc["tool_call_id"], "name": tc["tool_name"], "args": tc.get("input", {})}
                            for tc in raw_tool_calls if tc.get("tool_call_id")
                        ]
                    if tool_calls:
                        msg = AIMessage(content=m.content, tool_calls=tool_calls)
                    else:
                        msg = AIMessage(content=m.content)
                    history.append(msg)
                    if tool_calls:
                        for tc in raw_tool_calls:
                            if tc.get("tool_call_id") and tc.get("output") is not None:
                                history.append(ToolMessage(
                                    content=json.dumps(tc["output"]),
                                    tool_call_id=tc["tool_call_id"],
                                ))
            logger.info("BUILT HISTORY: %d messages from session %s", len(history), session.id)
            if history:
                logger.info("HISTORY ROLES: %s", [type(m).__name__ + ":" + (getattr(m, "content", "") or "")[:60] for m in history])
            return history
        except Exception as exc:
            logger.exception("FAILED to load history for session %s: %s", session.id, exc)
            return []

    async def _load_rag_context(
        self,
        agent_collection_repo: AgentCollectionRepository,
        chunk_repo: DocumentChunkRepository,
        agent: Agent,
        query: str,
    ) -> tuple[str | None, list[SourceInfo]]:
        try:
            collections = await agent_collection_repo.list_by_agent(agent.id)
            if not collections:
                return None, []

            all_sources: list[SourceInfo] = []
            all_chunks: list[str] = []

            for link in collections:
                try:
                    results = await chunk_repo.search_similar(
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
                            document_id=str(chunk.document_id) if chunk.document_id else None,
                            chunk_id=str(chunk.id),
                            page_number=chunk.page_number,
                            score=round(score, 4),
                            content_preview=chunk.content[:200],
                        )
                    )

            if not all_chunks:
                return None, []

            context = "\n\n".join(all_chunks)
            return context, all_sources
        except Exception:
            return None, []

    def _get_response_format(self, agent: Agent) -> dict:
        settings = agent.settings or {}
        return settings.get("response_format", {})

    def _clean_json_answer(self, answer: str) -> str:
        cleaned = answer.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return cleaned.strip()

    def _build_messages(
        self,
        agent: Agent,
        rag_context: str | None,
        history: list,
        user_message: str,
        response_format: dict | None = None,
    ) -> list:
        messages = []

        system_prompt = agent.system_prompt or ""

        if response_format:
            schema_json = json.dumps(response_format.get("schema", {}), indent=2)
            json_instruction = (
                "\n\nYou must respond with valid JSON only.\n"
                "Do not include markdown code blocks.\n"
                "Do not include explanations outside the JSON.\n"
                "The JSON must follow this schema:\n"
                f"<schema>\n{schema_json}\n</schema>"
            )
            system_prompt += json_instruction

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        if rag_context:
            messages.append(
                SystemMessage(
                    content=(
                        "Use the following context when relevant. "
                        "If the context is not enough, say you do not know.\n\n"
                        f"<context>\n{rag_context}\n</context>"
                    )
                )
            )

        messages.extend(history)
        messages.append(HumanMessage(content=user_message))
        return messages


