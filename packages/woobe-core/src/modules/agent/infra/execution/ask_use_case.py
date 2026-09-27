from __future__ import annotations

from copy import deepcopy

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
    AskOutput,
    SourceInfo,
    ToolCallInfo,
    UsageInfo,
)
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.llm_factory import LLMFactory
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.interfaces.repositories import (
    MessageRepository,
    ProviderCredentialRepository,
    SessionRepository,
)
from modules.agent.application.interfaces.tool_executor import ToolExecutor
from modules.agent.application.tool_converter import (
    MCP_PROVIDER_ROUTE_SEPARATOR,
    agent_tools_to_openai_definitions_and_mapping,
)
from modules.agent.domain.entities import Agent, AgentRelease, Message, ProviderCredential, Session
from modules.agent.domain.enums import (
    MessageRole,
    RuntimeSessionMode as SessionMode,
    SessionStatus,
)
from modules.agent.domain.errors import AgentNotFoundError, CredentialNotFoundError
from modules.agent.domain.run import AgentRunStatus
from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionRequestedV1,
    AgentExecutionStartedV1,
    AgentExecutionToolCompletedV1,
    AgentFallbackTriggeredV1,
    AgentMessageCreatedV1,
)
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from shared.contracts.llm_usage import normalize_llm_usage
from shared.contracts.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret

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
        transactions: AgentRuntimeTransactionRunner,
        llm_factory: LLMFactory | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_executor_factory: Callable[[UUID, dict], Awaitable[dict]] | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self._transactions = transactions
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
                agent,
                api_key,
                base_url,
                response_format,
                json_enabled,
                has_tools,
                agent_tools,
                tool_name_to_id,
                messages,
                knowledge_query=input_dto.message,
                history=history,
            )
            llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)

            execution_context = current_execution.get()
            execution = (
                execution_context.execution
                if execution_context is not None
                else None
            )
            if isinstance(execution, InstrumentedExecution):
                sources = list(execution.sources)
                fallback_used = bool(execution.fallback_used)
                fallback_info_result = execution.fallback_info
                if fallback_info_result:
                    fallback_provider_val = fallback_info_result.get(
                        "fallback_provider"
                    )
                if execution.suspension is not None:
                    output = await self._suspend(
                        session=session,
                        agent=agent,
                        input_dto=input_dto,
                        trace_id=trace_id,
                        execution=execution,
                    )
                    output.latency_ms = round((time.monotonic() - started_at) * 1000)
                    return output

            answer = result.content if hasattr(result, "content") else str(result)

            parsed_output = None
            output_parse_error = None
            if json_enabled:
                try:
                    cleaned = self._clean_json_answer(answer)
                    parsed_output = json.loads(cleaned)
                except (json.JSONDecodeError, Exception) as exc:
                    output_parse_error = str(exc)
                    strict = response_format.get("strict", False)
                    if strict:
                        logger.warning(
                            "Strict JSON mode enabled but model returned invalid JSON for agent %s: %s",
                            agent.id,
                            exc,
                        )

            raw_usage = normalize_llm_usage(result)
            usage = UsageInfo(
                input_tokens=raw_usage["input_tokens"],
                output_tokens=raw_usage["output_tokens"],
                total_tokens=raw_usage["total_tokens"],
                cost_usd=raw_usage["cost_usd"],
            )

            response_meta = getattr(result, "response_metadata", None) or {}
            response_model = response_meta.get(
                "model",
                agent.fallback_model if fallback_used else agent.model,
            )
            if fallback_used and fallback_provider_val:
                response_provider = response_meta.get("provider", fallback_provider_val)
            else:
                response_provider = response_meta.get(
                    "provider",
                    agent.provider.value
                    if hasattr(agent.provider, "value")
                    else agent.provider,
                )

            output = await self._finalize(
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
            output.latency_ms = round((time.monotonic() - started_at) * 1000)
            return output

        except Exception as exc:
            llm_error = str(exc)

            execution_context = current_execution.get()
            failed_execution = (
                execution_context.execution
                if execution_context is not None
                else None
            )
            if isinstance(failed_execution, InstrumentedExecution):
                sources = list(failed_execution.sources)

            # Fallback is an ExecutionStrategy decision. The outer runtime only
            # persists the terminal failure when the selected Strategy cannot
            # complete through its bound capabilities.
            await self._fail(trace_id, agent, session, llm_error, input_dto)
            raise ValueError(f"AI provider error: {llm_error}") from exc

    async def _suspend(
        self,
        *,
        session: Session | None,
        agent: Agent,
        input_dto: AskInput,
        trace_id: UUID,
        execution: InstrumentedExecution,
    ) -> AskOutput:
        suspension = execution.suspension
        if suspension is None:
            raise RuntimeError("Suspension persistence requires suspension evidence")

        context = current_execution.get()
        payload = {
            "reason": suspension.reason,
            "operation_ref": suspension.operation_ref,
            "metadata": dict(suspension.metadata or {}),
        }

        async def persist_waiting(
            repositories: AgentRuntimeRepositories,
            _outbox: OutboxEventWriter,
        ) -> None:
            if context is not None and context.run_id is not None:
                run = await repositories.runs.get_by_id(context.run_id)
                if run is not None and run.status in {
                    AgentRunStatus.RUNNING,
                    AgentRunStatus.WAITING,
                }:
                    run.status = AgentRunStatus.WAITING
                    run.result = {"suspension": payload}
                    run.failure_code = None
                    run.failure_detail = None
                    run.completed_at = None
                    await repositories.runs.save(run)

            if session is not None:
                current_session = await repositories.sessions.get_by_id(session.id)
                if current_session is not None:
                    current_session.status = SessionStatus.WAITING
                    await repositories.sessions.update(current_session)

        await self._transactions.run(persist_waiting)

        recorder = (
            context.run_event_recorder
            if context is not None
            else None
        )
        if recorder is not None:
            await recorder.emit(
                "execution.suspended",
                payload,
                durable=True,
            )

        hot_update = getattr(self, "_hot_update", None)
        if callable(hot_update):
            await hot_update(
                {
                    "status": "waiting",
                    "phase": "suspended",
                    "suspension": payload,
                }
            )

        return AskOutput(
            run_id=context.run_id if context is not None else None,
            status="waiting",
            answer="",
            suspension=payload,
            session_id=session.id if session is not None else None,
            trace_id=trace_id,
            sources=list(execution.sources),
            tool_calls=list(execution.tool_calls),
        )

    async def _prepare(
        self,
        input_dto: AskInput,
    ) -> tuple[
        Agent,
        Session | None,
        UUID,
        str,
        str | None,
        dict,
        bool,
        list[dict],
        dict[str, str],
        bool,
        list[SourceInfo],
        list,
        list,
    ]:
        async def prepare(repositories: AgentRuntimeRepositories, outbox: OutboxEventWriter):
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
                if session and self._uses_session_history(agent)
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

            # Knowledge retrieval is an ExecutionStrategy decision. Preparation
            # only builds the base conversation; the frozen Knowledge binding is
            # resolved by the durable runtime and exposed through StrategyKnowledge.
            sources: list[SourceInfo] = []
            messages = self._build_messages(
                agent,
                None,
                history,
                input_dto.message,
                response_format if json_enabled else None,
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
                sources,
                messages,
                history,
            )

        return await self._transactions.run(prepare)

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
        knowledge_query: str | None = None,
        history: list[Any] | tuple[Any, ...] | None = None,
    ) -> tuple[Any, list[ToolCallInfo], bool, int | None]:
        chat_model = self._llm_factory.create_chat_model(
            provider=(
                agent.provider.value if hasattr(agent.provider, "value") else agent.provider
            ),
            model=agent.model,
            api_key=api_key,
            base_url=base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"}
            if (json_enabled and not has_tools)
            else None,
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
            for tool_call in getattr(result, "tool_calls", None) or []:
                tool_start = time.monotonic()
                resolved_tool_id = tool_name_to_id.get(
                    tool_call["name"],
                    tool_call["name"],
                )
                tool_output = await self._execute_single_tool(
                    tool_call,
                    resolved_tool_id,
                )
                tool_duration = round((time.monotonic() - tool_start) * 1000)
                tool_success = (
                    tool_output.get("success", False)
                    if isinstance(tool_output, dict)
                    else True
                )
                tool_error = (
                    tool_output.get("error")
                    if isinstance(tool_output, dict)
                    else None
                )
                tool_calls_recorded.append(
                    ToolCallInfo(
                        tool_call_id=tool_call["id"],
                        tool_name=tool_call["name"],
                        input=tool_call.get("args"),
                        output=tool_output,
                        duration_ms=tool_duration,
                        success=tool_success,
                        error=tool_error,
                    )
                )
                messages.append(
                    ToolMessage(
                        content=(
                            json.dumps(tool_output)
                            if isinstance(tool_output, dict)
                            else str(tool_output)
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )

            tool_call_rounds += 1
            try:
                result = await chat_model.ainvoke(messages)
            except Exception as tool_error:
                logger.warning("Tool call follow-up LLM invoke failed: %s", tool_error)
                break

        if json_enabled and tool_was_called:
            try:
                answer_text = (
                    result.content if hasattr(result, "content") else str(result)
                )
                schema_json = json.dumps(response_format.get("schema", {}), indent=2)
                json_model = self._llm_factory.create_chat_model(
                    provider=(
                        agent.provider.value
                        if hasattr(agent.provider, "value")
                        else agent.provider
                    ),
                    model=agent.model,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=0.0,
                    max_tokens=agent.max_output_tokens or 1000,
                    response_format={"type": "json_object"},
                )
                await json_model.ainvoke(
                    [
                        SystemMessage(
                            content=(
                                "Responda APENAS com JSON válido seguindo este schema.\n"
                                "NÃO inclua markdown, explicações ou texto fora do JSON.\n"
                                f"<schema>\n{schema_json}\n</schema>"
                            )
                        ),
                        HumanMessage(
                            content=(
                                "Converta a resposta abaixo para JSON válido:\n\n"
                                f"{answer_text}"
                            )
                        ),
                    ]
                )
            except Exception as json_error:
                logger.warning(
                    "JSON formatting phase (Fase 2) failed: %s",
                    json_error,
                )

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
                tool_event = AgentExecutionToolCompletedV1.create(
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
                "sources": [source.model_dump() for source in sources]
                if sources
                else None,
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "tool_calls": [
                    tool_call.model_dump() for tool_call in tool_calls_recorded
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

    async def _fail(
        self,
        trace_id: UUID | None,
        agent: Agent,
        session: Session | None,
        error: str,
        input_dto: AskInput,
    ) -> None:
        async def persist_failure(
            _repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> None:
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

        try:
            await self._transactions.run(persist_failure)
        except Exception as exc:
            logger.warning("Failed to emit AgentExecutionFailedV1: %s", exc)

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        if not self._tool_executor and not self._tool_executor_factory:
            return {"success": False, "error": "Tool execution not available"}
        try:
            args = tool_call.get("args", {}) or {}
            execution_tool_id = tool_id
            if MCP_PROVIDER_ROUTE_SEPARATOR in tool_id:
                execution_tool_id, remote_tool_name = tool_id.split(
                    MCP_PROVIDER_ROUTE_SEPARATOR,
                    1,
                )
                args = {**args, "__mcp_tool_name": remote_tool_name}
            if self._tool_executor_factory:
                return await self._tool_executor_factory(UUID(execution_tool_id), args)
            return await self._tool_executor.execute_tool(UUID(execution_tool_id), args)
        except Exception as exc:
            logger.warning("Tool execution failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _load_agent(
        self,
        repositories: AgentRuntimeRepositories,
        input_dto: AskInput,
    ) -> Agent:
        agent = await repositories.agents.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        if (
            hasattr(agent, "status")
            and agent.status
            and hasattr(agent.status, "value")
            and agent.status.value != "active"
        ):
            from shared.contracts.errors import ValidationError

            raise ValidationError(f"Agent {input_dto.agent_id} is not active")

        if input_dto.execution_context == "production":
            release = await repositories.releases.get_active_production(agent.id)
            if release is None:
                raise ValueError(
                    f"No production release deployed for agent {input_dto.agent_id}"
                )
            agent = self._apply_release_to_agent(agent, release)
        elif input_dto.loaded_release_id:
            release = await repositories.releases.get_by_id(input_dto.loaded_release_id)
            if release:
                agent = self._apply_release_to_agent(agent, release)
        elif input_dto.snapshot_override:
            agent = self._apply_snapshot_override(agent, input_dto.snapshot_override)

        return agent

    def _apply_release_to_agent(self, agent: Agent, release: AgentRelease) -> Agent:
        agent.behavior_spec = deepcopy(getattr(release, "behavior_spec", None))
        if release.system_prompt is not None:
            agent.system_prompt = release.system_prompt
        if release.response_format is not None:
            settings = dict(agent.settings) if agent.settings else {}
            settings["response_format"] = release.response_format
            agent.settings = settings
        if release.provider is not None:
            from modules.agent.domain.enums import Provider

            agent.provider = (
                Provider(release.provider)
                if isinstance(release.provider, str)
                else release.provider
            )
        if release.model is not None:
            agent.model = release.model
        if release.provider_credential_id is not None:
            agent.provider_credential_id = release.provider_credential_id
        if release.fallback_provider is not None:
            from modules.agent.domain.enums import Provider

            agent.fallback_provider = (
                Provider(release.fallback_provider)
                if isinstance(release.fallback_provider, str)
                else release.fallback_provider
            )
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

            agent.session_mode = (
                SessionMode(release.session_mode)
                if isinstance(release.session_mode, str)
                else release.session_mode
            )
        if release.collection_ids is not None:
            pass
        return agent

    def _apply_snapshot_override(self, agent: Agent, snapshot: dict) -> Agent:
        agent.behavior_spec = deepcopy(snapshot.get("behavior_spec"))
        if snapshot.get("system_prompt") is not None:
            agent.system_prompt = snapshot["system_prompt"]
        if snapshot.get("response_format") is not None:
            settings = dict(agent.settings) if agent.settings else {}
            settings["response_format"] = snapshot["response_format"]
            agent.settings = settings
        if snapshot.get("provider") is not None:
            from modules.agent.domain.enums import Provider

            agent.provider = (
                Provider(snapshot["provider"])
                if isinstance(snapshot["provider"], str)
                else snapshot["provider"]
            )
        if snapshot.get("model") is not None:
            agent.model = snapshot["model"]
        if snapshot.get("provider_credential_id") is not None:
            agent.provider_credential_id = (
                UUID(snapshot["provider_credential_id"])
                if isinstance(snapshot["provider_credential_id"], str)
                else snapshot["provider_credential_id"]
            )
        if snapshot.get("temperature") is not None:
            agent.temperature = snapshot["temperature"]
        if snapshot.get("max_output_tokens") is not None:
            agent.max_output_tokens = snapshot["max_output_tokens"]
        if snapshot.get("session_mode") is not None:
            from modules.agent.domain.enums import SessionMode

            agent.session_mode = (
                SessionMode(snapshot["session_mode"])
                if isinstance(snapshot["session_mode"], str)
                else snapshot["session_mode"]
            )
        if snapshot.get("fallback_provider"):
            from modules.agent.domain.enums import Provider

            agent.fallback_provider = (
                Provider(snapshot["fallback_provider"])
                if isinstance(snapshot["fallback_provider"], str)
                else snapshot["fallback_provider"]
            )
        if snapshot.get("fallback_model"):
            agent.fallback_model = snapshot["fallback_model"]
        if snapshot.get("fallback_credential_id"):
            agent.fallback_credential_id = (
                UUID(snapshot["fallback_credential_id"])
                if isinstance(snapshot["fallback_credential_id"], str)
                else snapshot["fallback_credential_id"]
            )
        return agent

    async def _load_credential(
        self,
        credential_repo: ProviderCredentialRepository,
        agent: Agent,
    ) -> ProviderCredential:
        if not agent.provider_credential_id:
            from shared.contracts.errors import ValidationError

            raise ValidationError("Agent has no provider credential configured")
        return await self._load_credential_by_id(
            credential_repo,
            agent.provider_credential_id,
        )

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as exc:
            logger.error("Failed to decrypt credential %s: %s", credential.id, exc)
            from shared.contracts.errors import ValidationError

            raise ValidationError(
                "Provider credential secret could not be decrypted. Recreate the credential."
            )

    def _resolve_base_url(
        self,
        agent: Agent,
        credential: ProviderCredential,
    ) -> str | None:
        provider_val = (
            agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        )
        return self._resolve_base_url_for_provider(
            provider_val,
            credential,
            agent.settings,
        )

    async def _resolve_session(
        self,
        session_repo: SessionRepository,
        input_dto: AskInput,
        agent: Agent,
    ) -> Session:
        if input_dto.session_id:
            try:
                found = await session_repo.get_by_id(input_dto.session_id)
                logger.info("RESOLVE SESSION: found existing session %s", found.id)
                return found
            except Exception as exc:
                logger.warning(
                    "RESOLVE SESSION: get_by_id failed for %s: %s",
                    input_dto.session_id,
                    exc,
                )

        mode = (
            agent.session_mode.value
            if hasattr(agent.session_mode, "value")
            else agent.session_mode
        )
        logger.info("RESOLVE SESSION: agent mode=%s, will create new", mode)
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
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        session: Session,
        content: str,
        agent: Agent,
    ) -> Message:
        message = Message(
            project_id=session.project_id,
            agent_id=agent.id,
            session_id=session.id,
            role=MessageRole.USER,
            content=content,
        )
        created = await message_repo.create(message)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception as exc:
            logger.warning(
                "Failed to update session after saving user message: %s",
                exc,
            )
        return created

    async def _do_save_assistant_message(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        outbox: OutboxEventWriter,
        session: Session,
        content: str,
        usage: UsageInfo,
        agent: Agent,
        tool_calls: list[ToolCallInfo] | None = None,
    ) -> Message:
        message = Message(
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
            data={
                "tool_calls": [tool_call.model_dump() for tool_call in tool_calls]
                if tool_calls
                else None,
            }
            if tool_calls
            else None,
        )
        created = await message_repo.create(message)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception as exc:
            logger.warning(
                "Failed to update session after saving assistant message: %s",
                exc,
            )

        event = AgentMessageCreatedV1.create(
            message_id=created.id,
            session_id=session.id,
            project_id=session.project_id,
            agent_id=session.agent_id,
            role="assistant",
        )
        await outbox.write(event)
        return created

    @staticmethod
    def _uses_session_history(agent: Agent) -> bool:
        return str(getattr(agent.session_mode, "value", agent.session_mode)) != "stateless"

    async def _load_history(
        self,
        message_repo: MessageRepository,
        session: Session,
    ) -> list:
        try:
            messages = await message_repo.list_by_session(session.id)
            logger.debug(
                "Loaded %d raw messages from DB for session %s",
                len(messages),
                session.id,
            )
            history = []
            for message in messages:
                role = (
                    message.role.value
                    if hasattr(message.role, "value")
                    else message.role
                )
                if role == "user":
                    history.append(HumanMessage(content=message.content))
                elif role == "assistant":
                    raw_tool_calls = (message.data or {}).get("tool_calls") or []
                    tool_calls = None
                    if raw_tool_calls:
                        tool_calls = [
                            {
                                "id": tool_call["tool_call_id"],
                                "name": tool_call["tool_name"],
                                "args": tool_call.get("input", {}),
                            }
                            for tool_call in raw_tool_calls
                            if tool_call.get("tool_call_id")
                        ]
                    if tool_calls:
                        history_message = AIMessage(
                            content=message.content,
                            tool_calls=tool_calls,
                        )
                    else:
                        history_message = AIMessage(content=message.content)
                    history.append(history_message)
                    if tool_calls:
                        for tool_call in raw_tool_calls:
                            if (
                                tool_call.get("tool_call_id")
                                and tool_call.get("output") is not None
                            ):
                                history.append(
                                    ToolMessage(
                                        content=json.dumps(tool_call["output"]),
                                        tool_call_id=tool_call["tool_call_id"],
                                    )
                                )
            logger.info(
                "BUILT HISTORY: %d messages from session %s",
                len(history),
                session.id,
            )
            if history:
                logger.info(
                    "HISTORY ROLES: %s",
                    [
                        type(message).__name__
                        + ":"
                        + (getattr(message, "content", "") or "")[:60]
                        for message in history
                    ],
                )
            return history
        except Exception as exc:
            logger.exception(
                "FAILED to load history for session %s: %s",
                session.id,
                exc,
            )
            return []

    def _build_messages(
        self,
        agent: Agent,
        _rag_context: str | None,
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

        messages.extend(history)
        messages.append(HumanMessage(content=user_message))
        return messages

    def _get_response_format(self, agent: Agent) -> dict:
        settings = agent.settings or {}
        return settings.get("response_format", {})

    def _clean_json_answer(self, answer: str) -> str:
        cleaned = answer.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    async def _load_credential_by_id(
        self,
        credential_repo: ProviderCredentialRepository,
        credential_id: UUID,
    ) -> ProviderCredential:
        credential = await credential_repo.get_by_id(credential_id)
        if not credential:
            raise CredentialNotFoundError(credential_id)
        return credential

    def _resolve_base_url_for_provider(
        self,
        provider_val: str,
        credential: ProviderCredential,
        settings: dict | None,
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
            model = (
                (settings or {}).get("model")
                or (credential.metadata or {}).get("model")
            )
            if not model:
                from shared.contracts.errors import ValidationError

                raise ValidationError(
                    "Custom provider requires model in agent or credential metadata"
                )
            return base_url
        return None

    async def _try_fallback(
        self,
        agent: Agent,
        messages: list,
        json_enabled: bool,
        primary_error: str,
    ) -> tuple[Any, str, int, dict]:
        fallback_provider_val = (
            agent.fallback_provider.value
            if hasattr(agent.fallback_provider, "value")
            else agent.fallback_provider
        )

        fallback_api_key: str | None = None
        fallback_base_url: str | None = None
        if agent.fallback_credential_id:
            async def load_fallback(
                repositories: AgentRuntimeRepositories,
                _outbox: OutboxEventWriter,
            ):
                return await repositories.provider_credentials.get_by_id(
                    agent.fallback_credential_id
                )

            try:
                credential = await self._transactions.run(load_fallback)
                if credential:
                    fallback_api_key = self._decrypt_api_key(credential)
                    fallback_base_url = self._resolve_base_url_for_provider(
                        fallback_provider_val,
                        credential,
                        agent.settings,
                    )
            except Exception as exc:
                logger.warning("Failed to load fallback credential: %s", exc)

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
            "primary_provider": (
                agent.provider.value
                if hasattr(agent.provider, "value")
                else agent.provider
            ),
            "primary_error": primary_error,
            "fallback_model": agent.fallback_model,
            "fallback_provider": fallback_provider_val,
            "fallback_credential_id": str(agent.fallback_credential_id),
        }
        return (
            fallback_result,
            fallback_provider_val,
            fallback_latency,
            fallback_info,
        )
