from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.handlers.conversation_history_mapper import load_and_convert_history
from modules.agent.application.handlers.session_resolver import SessionResolver

from modules.agent.domain.entities import Agent, AgentRelease, ProviderCredential
from modules.agent.domain.errors import AgentNotFoundError, CredentialNotFoundError
from modules.agent.domain.repositories import (
    AgentReleaseRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.agent.domain.ports.llm_factory import LLMFactory
from modules.agent.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
)
from modules.agent.domain.entities import Message, Session
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.repositories import MessageRepository, SessionRepository
from modules.agent.domain.ports.trace_recorder import TraceRecorder
from modules.agent.domain.ports.tool_executor import ToolExecutor
from modules.agent.domain.ports.tool_repository import ToolRepository as AgentToolRepository
from modules.agent.domain.ports.usage_recorder import UsageRecorder
from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
    AskOutput,
    SourceInfo,
    ToolCallInfo,
    UsageInfo,
)
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions, _safe_tool_name
from shared.messaging.outbox_writer import OutboxEventWriter
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
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        agent_collection_repo: AgentCollectionRepository,
        chunk_repo: DocumentChunkRepository,
        trace_recorder: TraceRecorder,
        usage_recorder: UsageRecorder,
        outbox: OutboxEventWriter,
        llm_factory: LLMFactory,
        tool_executor: ToolExecutor | None = None,
        tool_repo: AgentToolRepository | None = None,
        release_repo: AgentReleaseRepository | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._session_repo = session_repo
        self._session_resolver = SessionResolver(session_repo)
        self._message_repo = message_repo
        self._agent_collection_repo = agent_collection_repo
        self._chunk_repo = chunk_repo
        self._trace_recorder = trace_recorder
        self._usage_recorder = usage_recorder
        self._outbox = outbox
        self._llm_factory = llm_factory
        self._tool_executor = tool_executor
        self._tool_repo = tool_repo
        self._release_repo = release_repo
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(self, input_dto: AskInput) -> AskOutput:
        started_at = time.monotonic()
        trace_id: UUID | None = None

        agent = await self._load_agent(input_dto)

        credential = await self._load_credential(agent)
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
        if self._tool_repo:
            try:
                tools = await self._tool_repo.list_by_agent(agent.id, status="active")
                if tools:
                    agent_tools = agent_tools_to_openai_definitions(tools)
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
            response_format={"type": "json_object"} if (json_enabled and not has_tools) else None,
        )

        if has_tools:
            chat_model = chat_model.bind_tools(agent_tools, tool_choice="auto")

        session = await self._resolve_session(input_dto, agent)

        history_limit = self._get_history_limit(agent)
        history = await self._load_history(session, history_limit) if session else []

        if session:
            await self._save_user_message(session, input_dto.message, agent)

        trace_id = await self._create_trace(input_dto, agent, session)

        rag_context, sources = await self._load_rag_context(agent, input_dto.message)

        messages = self._build_messages(agent, rag_context, history, input_dto.message, response_format if json_enabled else None)

        fallback_used = False
        fallback_info_result: dict | None = None
        fallback_provider_val: str | None = None

        tool_calls_recorded: list[ToolCallInfo] = []
        tool_was_called = False
        json_format_latency_ms: int | None = None

        try:
            llm_latency_start = time.monotonic()
            result = await chat_model.ainvoke(messages)
            llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)

            tool_call_rounds = 0
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
                    try:
                        await self._trace_recorder.record_event(
                            trace_id=trace_id,
                            project_id=input_dto.project_id,
                            event_type="tool_call",
                            latency_ms=tool_duration,
                            payload={
                                "tool_name": tc["name"],
                                "input": tc.get("args"),
                                "output": tool_output,
                                "success": tool_success,
                                "error": tool_error,
                            },
                        )
                    except Exception:
                        pass
                    messages.append(ToolMessage(
                        content=json.dumps(tool_output) if isinstance(tool_output, dict) else str(tool_output),
                        tool_call_id=tc["id"],
                    ))

                tool_call_rounds += 1
                try:
                    result = await chat_model.ainvoke(messages)
                    llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)
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
                    json_start = time.monotonic()
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
                    json_format_latency_ms = round((time.monotonic() - json_start) * 1000)
                    result = json_result

                    json_raw_usage = normalize_llm_usage(json_result)
                    try:
                        await self._trace_recorder.record_event(
                            trace_id=trace_id,
                            project_id=input_dto.project_id,
                            event_type="llm_call",
                            latency_ms=json_format_latency_ms,
                            payload={
                                "phase": "json_format",
                                "input_tokens": json_raw_usage["input_tokens"],
                                "output_tokens": json_raw_usage["output_tokens"],
                                "total_tokens": json_raw_usage["total_tokens"],
                                "cost_usd": json_raw_usage["cost_usd"],
                                "model": agent.model,
                                "provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                            },
                        )
                    except Exception:
                        pass
                except Exception as json_e:
                    logger.warning("JSON formatting phase (Fase 2) failed: %s", json_e)

        except Exception as e:
            primary_error = str(e)

            if agent.fallback_model and agent.fallback_credential_id:
                try:
                    await self._emit_fallback_triggered_event(trace_id, agent, primary_error)
                    fallback_result, fb_provider_val, fallback_latency, fallback_info_result = await self._try_fallback(
                        agent, messages, json_enabled, primary_error,
                    )
                    result = fallback_result
                    llm_latency_ms = fallback_latency
                    fallback_used = True
                    fallback_provider_val = fb_provider_val
                except Exception as fb_e:
                    combined_error = f"Primary: {primary_error} | Fallback: {fb_e}"
                    if trace_id:
                        await self._trace_recorder.fail_trace(trace_id, combined_error)
                    raise ValueError(f"AI provider error: {combined_error}") from fb_e
            else:
                if trace_id:
                    await self._trace_recorder.fail_trace(trace_id, primary_error)
                raise ValueError(f"AI provider error: {primary_error}") from e

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
                        agent.id,
                        e,
                    )

        raw_usage = normalize_llm_usage(result)
        logger.info("LLM result usage debug", extra={
            "usage_metadata": getattr(result, "usage_metadata", None),
            "response_metadata_keys": list(getattr(result, "response_metadata", None) or {}),
            "raw_usage": raw_usage,
        })
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

        message_id = None
        if session:
            assistant_msg = await self._save_assistant_message(
                session, answer, usage, agent,
                tool_calls=tool_calls_recorded,
            )
            message_id = assistant_msg.id

        try:
            await self._usage_recorder.record_llm_request(
                project_id=input_dto.project_id,
                agent_id=agent.id,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                total_tokens=usage.total_tokens or 0,
                cost_usd=usage.cost_usd or 0.0,
                model=agent.model,
            )
        except Exception as e:
            logger.warning("Failed to record usage: %s", e)

        try:
            await self._trace_recorder.complete_trace(
                trace_id=trace_id,
                answer=answer,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                total_tokens=usage.total_tokens or 0,
                cost_usd=usage.cost_usd or 0.0,
                model=response_model,
                provider=response_provider,
                latency_ms=llm_latency_ms,
                message_id=message_id,
                sources=sources,
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
                tool_calls=[tc.model_dump() for tc in tool_calls_recorded] if tool_calls_recorded else [],
                fallback_used=fallback_used,
                fallback_info=fallback_info_result,
                json_format_latency_ms=json_format_latency_ms,
            )
        except Exception as e:
            logger.warning("Failed to complete trace: %s", e)

        total_latency = round((time.monotonic() - started_at) * 1000)

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
            latency_ms=total_latency,
            parsed_output=parsed_output,
            output_parse_error=output_parse_error,
        )

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        if not self._tool_executor:
            return {"success": False, "error": "Tool execution not available"}
        try:
            args = tool_call.get("args", {}) or {}
            return await self._tool_executor.execute_tool(UUID(tool_id), args)
        except Exception as e:
            logger.warning("Tool execution failed: %s", e)
            return {"success": False, "error": str(e)}

    async def _load_agent(self, input_dto: AskInput) -> Agent:
        agent = await self._agent_repo.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        if hasattr(agent, "status") and agent.status and hasattr(agent.status, "value") and agent.status.value != "active":
            from shared.infra.errors import ValidationError
            raise ValidationError(f"Agent {input_dto.agent_id} is not active")

        if input_dto.execution_context == "production":
            release = await self._get_production_release(input_dto.agent_id)
            if release is None:
                raise ValueError(f"No production release deployed for agent {input_dto.agent_id}")
            agent = self._apply_release_to_agent(agent, release)
        elif input_dto.loaded_release_id and self._release_repo:
            release = await self._release_repo.get_by_id(input_dto.loaded_release_id)
            if release:
                agent = self._apply_release_to_agent(agent, release)
        elif input_dto.snapshot_override:
            agent = self._apply_snapshot_override(agent, input_dto.snapshot_override)

        return agent

    async def _get_production_release(self, agent_id: UUID) -> AgentRelease | None:
        if not self._release_repo:
            return None
        return await self._release_repo.get_active_production(agent_id)

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

    async def _load_credential(self, agent: Agent) -> ProviderCredential:
        if not agent.provider_credential_id:
            from shared.infra.errors import ValidationError
            raise ValidationError(
                "Agent has no provider credential configured"
            )
        return await self._load_credential_by_id(agent.provider_credential_id)

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", credential.id, e)
            from shared.infra.errors import ValidationError
            raise ValidationError(
                "Provider credential secret could not be decrypted. Recreate the credential."
            )

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        provider_val = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        return self._resolve_base_url_for_provider(provider_val, credential, agent.settings)

    async def _resolve_session(
        self, input_dto: AskInput, agent: Agent
    ) -> Session | None:
        mode = agent.session_mode.value if hasattr(agent.session_mode, "value") else agent.session_mode
        return await self._session_resolver.resolve(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            session_id=input_dto.session_id,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            session_mode=mode,
        )

    async def _save_user_message(
        self, session: Session, content: str, agent: Agent
    ) -> Message:
        msg = Message(
            project_id=session.project_id,
            agent_id=agent.id,
            session_id=session.id,
            role=MessageRole.USER,
            content=content,
        )
        created = await self._message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await self._session_repo.update(session)
        except Exception:
            pass
        return created

    async def _save_assistant_message(
        self, session: Session, content: str, usage: UsageInfo, agent: Agent,
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
        created = await self._message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await self._session_repo.update(session)
        except Exception:
            pass

        await self._outbox.write(
            aggregate_type="message",
            aggregate_id=created.id,
            event_type="runtime.ask.completed",
            payload={
                "message_id": str(created.id),
                "session_id": str(session.id),
                "project_id": str(session.project_id),
                "agent_id": str(session.agent_id),
                "role": "assistant",
            },
        )
        return created

    async def _load_history(self, session: Session, limit: int = 100) -> list:
        return await load_and_convert_history(
            self._message_repo, session.id, session.id, limit=limit,
        )

    @staticmethod
    def _get_history_limit(agent: Agent) -> int:
        default = 100
        if not agent.settings:
            return default
        try:
            limit = int(agent.settings.get("history_max_messages", default))
            return max(10, min(limit, 500))
        except (ValueError, TypeError):
            return default

    async def _load_rag_context(
        self, agent: Agent, query: str
    ) -> tuple[str | None, list[SourceInfo]]:
        try:
            collections = await self._agent_collection_repo.list_by_agent(agent.id)
            if not collections:
                return None, []

            all_sources: list[SourceInfo] = []
            all_chunks: list[str] = []

            for link in collections:
                try:
                    results = await self._chunk_repo.search_similar(
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

    def _get_response_format(self, agent: Agent) -> dict:
        settings = agent.settings or {}
        return settings.get("response_format", {})

    def _clean_json_answer(self, answer: str) -> str:
        cleaned = answer.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return cleaned.strip()

    async def _create_trace(
        self, input_dto: AskInput, agent: Agent, session: Session | None
    ) -> UUID:
        trace_id = await self._trace_recorder.create_trace(
            project_id=input_dto.project_id,
            agent_id=agent.id,
            session_id=session.id if session else None,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            model=agent.model,
        )

        try:
            await self._trace_recorder.record_event(
                trace_id=trace_id,
                project_id=input_dto.project_id,
                event_type="info",
                payload={"event": "ask.started", "message": input_dto.message[:200]},
            )
        except Exception:
            pass

        return trace_id

    async def _load_credential_by_id(self, credential_id: UUID) -> ProviderCredential:
        credential = await self._credential_repo.get_by_id(credential_id)
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
                from shared.infra.errors import ValidationError
                raise ValidationError(
                    "Custom provider requires base_url in credential metadata or agent settings"
                )
            model = (settings or {}).get("model") or (credential.metadata or {}).get("model")
            if not model:
                from shared.infra.errors import ValidationError
                raise ValidationError(
                    "Custom provider requires model in agent or credential metadata"
                )
            return base_url
        return None

    async def _try_fallback(
        self, agent: Agent, messages: list, json_enabled: bool, primary_error: str
    ) -> tuple[Any, str, int, dict]:
        fallback_provider_val = agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider
        fallback_credential = await self._load_credential_by_id(agent.fallback_credential_id)
        fallback_api_key = self._decrypt_api_key(fallback_credential)
        fallback_base_url = self._resolve_base_url_for_provider(
            fallback_provider_val, fallback_credential, agent.settings
        )

        fallback_chat_model = self._llm_factory.create_chat_model(
            provider=fallback_provider_val,
            model=agent.fallback_model,
            api_key=fallback_api_key,
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

    async def _emit_fallback_triggered_event(self, trace_id: UUID | None, agent: Agent, error: str) -> None:
        if not trace_id:
            return
        try:
            await self._trace_recorder.record_event(
                trace_id=trace_id,
                project_id=agent.project_id,
                event_type="info",
                payload={
                    "event": "ask.fallback_triggered",
                    "primary_model": agent.model,
                    "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                    "primary_error": error,
                    "fallback_model": agent.fallback_model,
                    "fallback_provider": agent.fallback_provider.value if hasattr(agent.fallback_provider, "value") else agent.fallback_provider,
                },
            )
        except Exception as e:
            logger.warning("Failed to emit fallback triggered event: %s", e)

    async def _fail_trace(self, trace_id: UUID | None, error: str) -> None:
        if not trace_id:
            return
        try:
            await self._trace_recorder.fail_trace(trace_id, error)
        except Exception as e:
            logger.warning("Failed to fail trace %s: %s", trace_id, e)

    async def _complete_trace(
        self,
        trace_id: UUID | None,
        answer: str,
        usage: UsageInfo,
        model: str,
        provider: str,
        latency_ms: float | None,
        message_id: UUID | None = None,
        sources: list[SourceInfo] | None = None,
        parsed_output: dict | None = None,
        output_parse_error: str | None = None,
        tool_calls: list | None = None,
        fallback_used: bool = False,
        fallback_info: dict | None = None,
        json_format_latency_ms: int | None = None,
    ) -> None:
        if not trace_id:
            return
        try:
            await self._trace_recorder.complete_trace(
                trace_id=trace_id,
                answer=answer,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                total_tokens=usage.total_tokens or 0,
                cost_usd=usage.cost_usd or 0.0,
                model=model,
                provider=provider,
                latency_ms=latency_ms,
                message_id=message_id,
                sources=sources,
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
                tool_calls=tool_calls,
                fallback_used=fallback_used,
                fallback_info=fallback_info,
                json_format_latency_ms=json_format_latency_ms,
            )
        except Exception as e:
            logger.warning("Failed to complete trace %s: %s", trace_id, e)

    async def _record_usage(
        self, input_dto: AskInput, agent: Agent, usage: UsageInfo
    ) -> None:
        pass
