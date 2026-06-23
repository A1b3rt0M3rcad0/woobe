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
from modules.agent.domain.ports.llm_factory import LLMFactory
from modules.agent.domain.ports.tool_executor import ToolExecutor
from modules.agent.domain.repositories import (
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
from shared.infra.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.infra.llm_usage import normalize_llm_usage

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
            from shared.infra.errors import ValidationError
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
        return agent

    async def _load_credential(self, repo: ProviderCredentialRepository, agent: Agent) -> ProviderCredential:
        cred = await repo.get_by_id(agent.provider_credential_id) if agent.provider_credential_id else None
        if not cred or cred.project_id != agent.project_id:
            raise CredentialNotFoundError(agent.provider_credential_id or UUID(int=0))
        if hasattr(cred, "status") and cred.status and hasattr(cred.status, "value") and cred.status.value != "active":
            from shared.infra.errors import ValidationError
            raise ValidationError("Provider credential is not active")
        return cred

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        return decrypt_secret(credential.encrypted_secret, self._encryption_key)

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        if credential.metadata and credential.metadata.get("base_url"):
            return str(credential.metadata.get("base_url"))
        return None

    def _get_response_format(self, agent: Agent) -> dict:
        settings = dict(agent.settings) if agent.settings else {}
        response_format = settings.get("response_format") or {}
        if isinstance(response_format, dict):
            return response_format
        return {}

    def _clean_json_answer(self, answer: str) -> str:
        answer = re.sub(r"```json\s*", "", answer)
        answer = re.sub(r"```\s*", "", answer)
        return answer.strip()

    def _build_messages(self, agent: Agent, rag_context: str, history: list[Message], message: str, response_format: dict | None) -> list:
        messages: list = []
        system_content = agent.system_prompt or "You are a helpful AI assistant."
        if rag_context:
            system_content += f"\n\nRelevant context:\n{rag_context}"
        if response_format:
            schema = response_format.get("schema") or {}
            system_content += (
                "\n\nYou must respond with valid JSON matching this schema. "
                "Do not include markdown fences or explanatory text outside JSON.\n"
                f"Schema: {json.dumps(schema)}"
            )
        messages.append(SystemMessage(content=system_content))
        for msg in history[-20:]:
            if msg.role == MessageRole.USER:
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=message))
        return messages

    async def _load_history(self, repo: MessageRepository, session: Session) -> list[Message]:
        return await repo.list_by_session(session.id, limit=50)

    async def _save_user_message(self, session_repo: SessionRepository, message_repo: MessageRepository, session: Session, content: str, agent: Agent) -> None:
        await message_repo.create(Message(
            project_id=agent.project_id,
            agent_id=agent.id,
            session_id=session.id,
            role=MessageRole.USER,
            content=content,
        ))

    async def _save_assistant_message(self, repo: MessageRepository, session: Session, content: str, usage: UsageInfo) -> None:
        await repo.create(Message(
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        ))

    async def _do_save_assistant_message(self, message_repo: MessageRepository, session_repo: SessionRepository, outbox: SQLAlchemyAgentOutboxEventWriter, session: Session, answer: str, usage: UsageInfo, agent: Agent, tool_calls=None) -> Message:
        msg = Message(
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            data={"tool_calls": [tc.model_dump() for tc in tool_calls]} if tool_calls else None,
        )
        created = await message_repo.create(msg)
        session.last_message_at = utc_now()
        await session_repo.update(session)
        event = AgentMessageCreatedV1.create(
            agent_id=agent.id,
            session_id=session.id,
            payload={"message_id": str(created.id), "role": "assistant", "content_preview": answer[:200]},
        )
        await outbox.write(event)
        return created

    async def _load_rag_context(self, agent: Agent, query: str, uow: AgentUnitOfWork) -> tuple[str, list[SourceInfo]]:
        try:
            collection_repo = SQLAlchemyAgentCollectionRepository(uow)
            links = await collection_repo.list_by_agent(agent.id)
            if not links:
                return "", []
            collection_ids = [l.collection_id for l in links]
            from modules.agent.infra.database.repositories import SQLAlchemyDocumentChunkRepository
            chunk_repo = SQLAlchemyDocumentChunkRepository(uow)
            chunks = await chunk_repo.search(query, collection_ids, limit=5)
            sources = [SourceInfo(
                document_id=c.document_id,
                chunk_id=c.id,
                title=c.section_title or "Document",
                score=1.0,
            ) for c in chunks]
            context = "\n\n".join(c.content for c in chunks)
            return context, sources
        except Exception as e:
            logger.warning("RAG context load failed: %s", e)
            return "", []
