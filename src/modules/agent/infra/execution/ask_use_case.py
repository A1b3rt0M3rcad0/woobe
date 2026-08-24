from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.domain.entities import Agent, AgentRelease, ProviderCredential
from modules.agent.domain.entities import Message, Session
from modules.agent.domain.enums import MessageRole, RuntimeSessionMode as SessionMode
from modules.agent.domain.errors import AgentNotFoundError, CredentialNotFoundError
from modules.agent.application.interfaces.llm_factory import LLMFactory
from modules.agent.application.interfaces.tool_executor import ToolExecutor
from modules.agent.application.interfaces.repositories import (
    ProviderCredentialRepository,
    MessageRepository,
    SessionRepository,
)
from modules.agent.domain.events import (
    AgentMessageCreatedV1,
    AgentExecutionRequestedV1,
    AgentExecutionStartedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionToolCompletedV1,
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentFallbackTriggeredV1,
)
from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
    AskOutput,
    SourceInfo,
    ToolCallInfo,
    UsageInfo,
)
from modules.agent.application.tool_converter import (
    MCP_PROVIDER_ROUTE_SEPARATOR,
    agent_tools_to_openai_definitions_and_mapping,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAgentReleaseRepository,
    SQLAlchemyAgentCollectionRepository,
)
from shared.contracts.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.contracts.llm_usage import normalize_llm_usage

logger = logging.getLogger(__name__)


def _has_tool_calls(result) -> bool:
    return bool(getattr(result, "tool_calls", None))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class AskAgentUseCase:

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        llm_factory: LLMFactory | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_executor_factory: Callable[[UUID, dict], Awaitable[dict]] | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._llm_factory = llm_factory
        self._tool_executor = tool_executor
        self._tool_executor_factory = tool_executor_factory
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(self, input_dto: AskInput) -> AskOutput:
        started_at = time.monotonic()

        return await self._execute_phased(input_dto, started_at)

    async def _execute_phased(self, input_dto: AskInput, started_at: float) -> AskOutput:
        agent, session, trace_id, api_key, base_url, response_format, json_enabled, \
            agent_tools, tool_name_to_id, has_tools, sources, messages, history \
            = await self._prepare(input_dto)

        fallback_used = False
        fallback_info_result: dict | None = None
        fallback_provider_val: str | None = None
        tool_calls_recorded: list[ToolCallInfo] = []
        json_format_latency_ms: int | None = None
        llm_error: str | None = None
        llm_latency_ms: int | None = None

        logger.info("SENDING TO LLM: %d messages", len(messages))
        for i, msg in enumerate(messages):
            role = type(msg).__name__
            content_preview = (getattr(msg, "content", "") or "")[:100]
            logger.info("  MSG[%d] %s: %s", i, role, content_preview)

        try:
            llm_latency_start = time.monotonic()
            result, tool_calls_recorded, _, _ = await self._execute_llm(
                agent, api_key, base_url, response_format, json_enabled, has_tools,
                agent_tools, tool_name_to_id, messages,
            )
            llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)

            answer = result.content if hasattr(result, "content") else str(result)

            parsed_output = None
            output_parse_error = None
            if json_enabled:
                try:
                    cleaned = self._clean_json_answer(answer)
                    parsed_output = json.loads(cleaned)
                except (json.JSONDecodeError, Exception) as e:
                    output_parse_error = str(e)
                    strict = response_format.get("strict", False)
                    if strict:
                        logger.warning(
                            "Strict JSON mode enabled but model returned invalid JSON for agent %s: %s",
                            agent.id, e,
                        )

            raw_usage = normalize_llm_usage(result)
            usage = UsageInfo(
                input_tokens=raw_usage["input_tokens"],
                output_tokens=raw_usage["output_tokens"],
                total_tokens=raw_usage["total_tokens"],
                cost_usd=raw_usage["cost_usd"],
            )

            response_meta = getattr(result, "response_metadata", None) or {}
            response_model = response_meta.get("model", agent.fallback_model if fallback_used else agent.model)
            if fallback_used and fallback_provider_val:
                response_provider = response_meta.get("provider", fallback_provider_val)
            else:
                response_provider = response_meta.get("provider", agent.provider.value if hasattr(agent.provider, "value") else agent.provider)

            output = await self._finalize(
                session, agent, input_dto, trace_id,
                answer, usage, response_model, response_provider,
                llm_latency_ms, sources, parsed_output, output_parse_error,
                tool_calls_recorded, fallback_used, fallback_info_result,
                json_format_latency_ms,
            )
            output.latency_ms = round((time.monotonic() - started_at) * 1000)
            return output

        except Exception as e:
            llm_error = str(e)

            if agent.fallback_model and agent.fallback_credential_id:
                try:
                    fallback_info_result = {
                        "primary_model": agent.model,
                        "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                        "primary_error": llm_error,
                        "fallback_model": agent.fallback_model,
                        "fallback_provider": agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider,
                    }
                    fallback_result, fb_provider_val, fallback_latency, fallback_info_result = await self._try_fallback(
                        agent, messages, json_enabled, llm_error,
                    )
                    llm_latency_ms = fallback_latency
                    fallback_used = True
                    fallback_provider_val = fb_provider_val

                    result = fallback_result
                    answer = result.content if hasattr(result, "content") else str(result)

                    parsed_output = None
                    output_parse_error = None
                    if json_enabled:
                        try:
                            cleaned = self._clean_json_answer(answer)
                            parsed_output = json.loads(cleaned)
                        except Exception:
                            pass

                    raw_usage = normalize_llm_usage(result)
                    usage = UsageInfo(
                        input_tokens=raw_usage["input_tokens"],
                        output_tokens=raw_usage["output_tokens"],
                        total_tokens=raw_usage["total_tokens"],
                        cost_usd=raw_usage["cost_usd"],
                    )

                    response_meta = getattr(result, "response_metadata", None) or {}
                    response_model = response_meta.get("model", agent.fallback_model)
                    response_provider = response_meta.get("provider", fallback_provider_val)

                    output = await self._finalize(
                        session, agent, input_dto, trace_id,
                        answer, usage, response_model, response_provider,
                        llm_latency_ms, sources, parsed_output, output_parse_error,
                        tool_calls_recorded, fallback_used, fallback_info_result,
                        json_format_latency_ms,
                    )
                    output.latency_ms = round((time.monotonic() - started_at) * 1000)
                    return output
                except Exception as fb_e:
                    combined_error = f"Primary: {llm_error} | Fallback: {fb_e}"
                    await self._fail(trace_id, agent, session, combined_error, input_dto)
                    raise ValueError(f"AI provider error: {combined_error}") from fb_e
            else:
                await self._fail(trace_id, agent, session, llm_error, input_dto)
                raise ValueError(f"AI provider error: {llm_error}")

    async def _prepare(
        self, input_dto: AskInput,
    ) -> tuple[Agent, Session | None, UUID, str, str | None, dict, bool, list[dict], dict[str, str], bool, list[SourceInfo], list, list]:
        async with AgentUnitOfWork(self._session_factory) as uow:
            trace_id = uuid4()

            credential_repo = uow.provider_credentials
            session_repo = uow.sessions
            message_repo = uow.messages
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)

            agent = await self._load_agent(uow, input_dto)

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
                tool_repo = uow.tools
                tools = await tool_repo.list_by_agent(agent.id, status="active")
                if tools:
                    agent_tools, tool_name_to_id = agent_tools_to_openai_definitions_and_mapping(tools)
                    has_tools = bool(agent_tools)
            except Exception as e:
                logger.warning("Failed to load tools for agent %s: %s", agent.id, e)

            session = await self._resolve_session(session_repo, input_dto, agent)
            history = await self._load_history(message_repo, session) if session else []

            if session:
                await self._save_user_message(session_repo, message_repo, session, input_dto.message, agent)

            rag_context, sources = await self._load_rag_context(agent, input_dto.message, uow)

            messages = self._build_messages(agent, rag_context, history, input_dto.message, response_format if json_enabled else None)

            execution_payload: dict[str, Any] = {
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id) if session else None,
                "model": agent.model,
                "provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
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

        return agent, session, trace_id, api_key, base_url, response_format, json_enabled, \
            agent_tools, tool_name_to_id, has_tools, sources, messages, history

    async def _execute_llm(
        self,
        agent: Agent,
        api_key: str,
        base_url: str | None,
        response_format: dict,
        json_enabled: bool,
        has_tools: bool,
        agent_tools: list[dict],
        tool_name_to_id: dict[str, str],
        messages: list,
    ) -> tuple[Any, list[ToolCallInfo], bool, int | None]:
        chat_model = self._llm_factory.create_chat_model(
            provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            model=agent.model,
            api_key=api_key,
            base_url=base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if (json_enabled and not has_tools) else None,
        )

        if has_tools:
            chat_model = chat_model.bind_tools(agent_tools, tool_choice="auto")

        tool_calls_recorded: list[ToolCallInfo] = []
        tool_was_called = False
        json_format_latency_ms: int | None = None

        tool_call_rounds = 0
        result = await chat_model.ainvoke(messages)

        while _has_tool_calls(result) and tool_call_rounds < 5:
            tool_was_called = True
            messages.append(result)
            for tc in (getattr(result, "tool_calls", None) or []):
                tool_start = time.monotonic()
                resolved_tool_id = tool_name_to_id.get(tc["name"], tc["name"])
                tool_output = await self._execute_single_tool(tc, resolved_tool_id)
                tool_duration = round((time.monotonic() - tool_start) * 1000)
                tool_success = tool_output.get("success", False) if isinstance(tool_output, dict) else True
                tool_error = tool_output.get("error") if isinstance(tool_output, dict) else None
                tool_calls_recorded.append(ToolCallInfo(
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    input=tc.get("args"),
                    output=tool_output,
                    duration_ms=tool_duration,
                    success=tool_success,
                    error=tool_error,
                ))
                messages.append(ToolMessage(
                    content=json.dumps(tool_output) if isinstance(tool_output, dict) else str(tool_output),
                    tool_call_id=tc["id"],
                ))

            tool_call_rounds += 1
            try:
                result = await chat_model.ainvoke(messages)
            except Exception as tool_e:
                logger.warning("Tool call follow-up LLM invoke failed: %s", tool_e)
                break

        if json_enabled and tool_was_called:
            try:
                answer_text = result.content if hasattr(result, "content") else str(result)
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
                await json_model.ainvoke([
                    SystemMessage(
                        content=(
                            "Responda APENAS com JSON válido seguindo este schema.\n"
                            "NÃO inclua markdown, explicações ou texto fora do JSON.\n"
                            f"<schema>\n{schema_json}\n</schema>"
                        )
                    ),
                    HumanMessage(content=f"Converta a resposta abaixo para JSON válido:\n\n{answer_text}"),
                ])
            except Exception as json_e:
                logger.warning("JSON formatting phase (Fase 2) failed: %s", json_e)

        return result, tool_calls_recorded, tool_was_called, json_format_latency_ms

    async def _finalize(
        self,
        session: Session | None,
        agent: Agent,
        input_dto: AskInput,
        trace_id: UUID,
        answer: str,
        usage: UsageInfo,
        response_model: str | None,
        response_provider: str | None,
        llm_latency_ms: int | None,
        sources: list[SourceInfo] | None,
        parsed_output: dict | None,
        output_parse_error: str | None,
        tool_calls_recorded: list[ToolCallInfo],
        fallback_used: bool,
        fallback_info_result: dict | None,
        json_format_latency_ms: int | None,
    ) -> AskOutput:
        async with AgentUnitOfWork(self._session_factory) as uow:
            message_repo = uow.messages
            session_repo = uow.sessions
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)

            message_id = None
            if session:
                assistant_msg = await self._do_save_assistant_message(
                    message_repo, session_repo, outbox,
                    session, answer, usage, agent,
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

            for tc in (tool_calls_recorded or []):
                tool_event = AgentExecutionToolCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload={
                        "trace_id": str(trace_id),
                        "tool_name": tc.tool_name,
                        "duration_ms": tc.duration_ms,
                        "success": tc.success,
                        "error": tc.error,
                    },
                )
                await outbox.write(tool_event)

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
                "sources": [s.model_dump() for s in sources] if sources else None,
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "tool_calls": [tc.model_dump() for tc in tool_calls_recorded] if tool_calls_recorded else [],
            }
            if fallback_info_result:
                completion_payload["fallback_info"] = fallback_info_result
                fallback_event = AgentFallbackTriggeredV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=fallback_info_result,
                )
                await outbox.write(fallback_event)

            completed_event = AgentExecutionCompletedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload=completion_payload,
            )
            await outbox.write(completed_event)

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

    async def _fail(
        self,
        trace_id: UUID | None,
        agent: Agent,
        session: Session | None,
        error: str,
        input_dto: AskInput,
    ) -> None:
        try:
            async with AgentUnitOfWork(self._session_factory) as uow:
                outbox = SQLAlchemyAgentOutboxEventWriter(uow)
                failed_event = AgentExecutionFailedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload={
                        "trace_id": str(trace_id) if trace_id else None,
                        "project_id": str(input_dto.project_id),
                        "agent_id": str(agent.id),
                        "error": error,
                    },
                )
                await outbox.write(failed_event)
        except Exception as e:
            logger.warning("Failed to emit AgentExecutionFailedV1: %s", e)

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        if not self._tool_executor and not self._tool_executor_factory:
            return {"success": False, "error": "Tool execution not available"}
        try:
            args = tool_call.get("args", {}) or {}
            execution_tool_id = tool_id
            if MCP_PROVIDER_ROUTE_SEPARATOR in tool_id:
                execution_tool_id, remote_tool_name = tool_id.split(MCP_PROVIDER_ROUTE_SEPARATOR, 1)
                args = {**args, "__mcp_tool_name": remote_tool_name}
            if self._tool_executor_factory:
                return await self._tool_executor_factory(UUID(execution_tool_id), args)
            return await self._tool_executor.execute_tool(UUID(execution_tool_id), args)
        except Exception as e:
            logger.warning("Tool execution failed: %s", e)
            return {"success": False, "error": str(e)}

    async def _load_agent(self, uow: AgentUnitOfWork, input_dto: AskInput) -> Agent:
        agent_repo = uow.agents
        agent = await agent_repo.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        if hasattr(agent, "status") and agent.status and hasattr(agent.status, "value") and agent.status.value != "active":
            from shared.contracts.errors import ValidationError
            raise ValidationError(f"Agent {input_dto.agent_id} is not active")

        if input_dto.execution_context == "production":
            release_repo = SQLAlchemyAgentReleaseRepository(uow)
            release = await release_repo.get_active_production(agent.id)
            if release is None:
                raise ValueError(f"No production release deployed for agent {input_dto.agent_id}")
            agent = self._apply_release_to_agent(agent, release)
        elif input_dto.loaded_release_id:
            release_repo = SQLAlchemyAgentReleaseRepository(uow)
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
        if release.collection_ids is not None:
            pass
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

    async def _load_credential(self, credential_repo: ProviderCredentialRepository, agent: Agent) -> ProviderCredential:
        if not agent.provider_credential_id:
            from shared.contracts.errors import ValidationError
            raise ValidationError(
                "Agent has no provider credential configured"
            )
        return await self._load_credential_by_id(credential_repo, agent.provider_credential_id)

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", credential.id, e)
            from shared.contracts.errors import ValidationError
            raise ValidationError(
                "Provider credential secret could not be decrypted. Recreate the credential."
            )

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        provider_val = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        return self._resolve_base_url_for_provider(provider_val, credential, agent.settings)

    async def _resolve_session(
        self, session_repo: SessionRepository, input_dto: AskInput, agent: Agent
    ) -> Session | None:
        if input_dto.session_id:
            try:
                found = await session_repo.get_by_id(input_dto.session_id)
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
        created = await session_repo.create(session)
        logger.info("RESOLVE SESSION: created new session %s", created.id)
        return created

    async def _save_user_message(
        self, session_repo: SessionRepository, message_repo: MessageRepository,
        session: Session, content: str, agent: Agent,
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
        except Exception as e:
            logger.warning("Failed to update session after saving user message: %s", e)
        return created

    async def _do_save_assistant_message(
        self, message_repo: MessageRepository, session_repo: SessionRepository,
        outbox: SQLAlchemyAgentOutboxEventWriter,
        session: Session, content: str, usage: UsageInfo, agent: Agent,
        tool_calls: list[ToolCallInfo] | None = None,
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
            } if tool_calls else None,
        )
        created = await message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception as e:
            logger.warning("Failed to update session after saving assistant message: %s", e)

        event = AgentMessageCreatedV1.create(
            message_id=created.id,
            session_id=session.id,
            project_id=session.project_id,
            agent_id=session.agent_id,
            role="assistant",
        )
        await outbox.write(event)
        return created

    async def _load_history(
        self, message_repo: MessageRepository, session: Session,
    ) -> list:
        try:
            messages = await message_repo.list_by_session(session.id)
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
        self, agent: Agent, query: str, uow: AgentUnitOfWork,
    ) -> tuple[str | None, list[SourceInfo]]:
        try:
            agent_collection_repo = SQLAlchemyAgentCollectionRepository(uow)
            collections = await agent_collection_repo.list_by_agent(agent.id)
            if not collections:
                return None, []

            all_sources: list[SourceInfo] = []
            all_chunks: list[str] = []
            chunk_repo = uow.document_chunks

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

    def _build_messages(
        self,
        agent: Agent,
        rag_context: str | None,
        history: list,
        user_message: str,
        response_format: dict | None = None
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

    def _get_response_format(self, agent: Agent) -> dict:
        settings = agent.settings or {}
        return settings.get("response_format", {})

    def _clean_json_answer(self, answer: str) -> str:
        cleaned = answer.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return cleaned.strip()

    async def _load_credential_by_id(
        self, credential_repo: ProviderCredentialRepository, credential_id: UUID,
    ) -> ProviderCredential:
        credential = await credential_repo.get_by_id(credential_id)
        if not credential:
            raise CredentialNotFoundError(credential_id)
        return credential

    def _resolve_base_url_for_provider(
        self, provider_val: str, credential: ProviderCredential, settings: dict | None
    ) -> str | None:
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
            model = (settings or {}).get("model") or (credential.metadata or {}).get("model")
            if not model:
                from shared.contracts.errors import ValidationError
                raise ValidationError(
                    "Custom provider requires model in agent or credential metadata"
                )
            return base_url
        return None

    async def _try_fallback(
        self, agent: Agent, messages: list, json_enabled: bool, primary_error: str,
    ) -> tuple[Any, str, int, dict]:
        fallback_provider_val = agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider

        fallback_api_key: str | None = None
        fallback_base_url: str | None = None
        if agent.fallback_credential_id:
            try:
                async with AgentUnitOfWork(self._session_factory) as fallback_uow:
                    credential = await fallback_uow.provider_credentials.get_by_id(agent.fallback_credential_id)
                    if credential:
                        fallback_api_key = self._decrypt_api_key(credential)
                        fallback_base_url = self._resolve_base_url_for_provider(
                            fallback_provider_val, credential, agent.settings,
                        )
            except Exception as e:
                logger.warning("Failed to load fallback credential: %s", e)

        fallback_chat_model = self._llm_factory.create_chat_model(
            provider=fallback_provider_val,
            model=agent.fallback_model,
            api_key=fallback_api_key or "",
            base_url=fallback_base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if json_enabled else None,
        )

        llm_start = time.monotonic()
        fallback_result = await fallback_chat_model.ainvoke(messages)
        fallback_latency = round((time.monotonic() - llm_start) * 1000)

        fallback_info = {
            "primary_model": agent.model,
            "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            "primary_error": primary_error,
            "fallback_model": agent.fallback_model,
            "fallback_provider": fallback_provider_val,
            "fallback_credential_id": str(agent.fallback_credential_id),
        }
        return fallback_result, fallback_provider_val, fallback_latency, fallback_info
