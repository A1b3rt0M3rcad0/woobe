from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.domain.entities import Agent, AgentRelease, ProviderCredential
from modules.ai.domain.errors import AgentNotFoundError, CredentialNotFoundError
from modules.ai.domain.repositories import (
    AgentReleaseRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.infra.llm.langchain_factory import create_chat_model
from modules.ai.infra.repositories import (
    SQLAlchemyAgentReleaseRepository,
    SQLAlchemyAgentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.knowledge.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
)
from modules.knowledge.infra.repositories import (
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyDocumentChunkRepository,
)
from modules.metering.domain.entities import UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.domain.repositories import UsageEventRepository
from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository
from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.domain.repositories import (
    TraceEventRepository,
    TraceRepository,
)
from modules.observability.infra.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.enums import MessageRole, SessionMode
from modules.runtime.domain.repositories import MessageRepository, SessionRepository
from modules.runtime.infra.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemySessionRepository,
)
from modules.runtime.service.dtos import (
    AskInput,
    SourceInfo,
    UsageInfo,
)
from shared.domain.events import OutboxEventWriter
from shared.domain.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.infra.llm_usage import normalize_llm_usage

logger = logging.getLogger(__name__)


class AskAgentStreamService:

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
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
            async with self._session_factory() as db_session:
                agent_repo: AgentRepository = SQLAlchemyAgentRepository(db_session)
                credential_repo: ProviderCredentialRepository = SQLAlchemyProviderCredentialRepository(db_session)
                session_repo: SessionRepository = SQLAlchemySessionRepository(db_session)
                message_repo: MessageRepository = SQLAlchemyMessageRepository(db_session)
                agent_collection_repo: AgentCollectionRepository = SQLAlchemyAgentCollectionRepository(db_session)
                chunk_repo: DocumentChunkRepository = SQLAlchemyDocumentChunkRepository(db_session)
                trace_repo: TraceRepository = SQLAlchemyTraceRepository(db_session)
                trace_event_repo: TraceEventRepository = SQLAlchemyTraceEventRepository(db_session)

                release_repo: AgentReleaseRepository = SQLAlchemyAgentReleaseRepository(db_session)

                agent = await self._load_agent(agent_repo, release_repo, input_dto)
                credential = await self._load_credential(credential_repo, agent)
                api_key = self._decrypt_api_key(credential)
                base_url = self._resolve_base_url(agent, credential)

                response_format = self._get_response_format(agent)
                json_enabled = (
                    response_format.get("enabled", False)
                    and response_format.get("type") == "json"
                )

                session = await self._resolve_session(session_repo, input_dto, agent)

                if session:
                    await self._save_user_message(message_repo, session_repo, session, input_dto.message, agent)

                trace_id = await self._create_trace(trace_repo, trace_event_repo, input_dto, agent, session)

                history: list = []
                if session:
                    history = await self._load_history(message_repo, session)

                rag_context, sources = await self._load_rag_context(agent_collection_repo, chunk_repo, agent, input_dto.message)

                messages = self._build_messages(agent, rag_context, history, input_dto.message, response_format if json_enabled else None)

                await db_session.commit()

                if sources:
                    yield self._sse_event("sources", {"sources": [s.model_dump() for s in sources]})

                yield self._sse_event("meta", {
                    "session_id": str(session.id) if session else None,
                    "trace_id": str(trace_id) if trace_id else None,
                })

            chat_model = create_chat_model(
                provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                model=agent.model,
                api_key=api_key,
                base_url=base_url,
                temperature=agent.temperature or 0.2,
                max_tokens=agent.max_output_tokens or 1000,
                streaming=True,
                response_format={"type": "json_object"} if json_enabled else None,
            )

            llm_latency_start = time.monotonic()
            accumulated: list[str] = []
            input_tokens: int | None = None
            output_tokens: int | None = None
            total_tokens: int | None = None

            async for chunk in chat_model.astream(messages):
                content = chunk.content if hasattr(chunk, "content") and chunk.content else ""
                if content:
                    accumulated.append(content)
                    yield self._sse_event("token", {"content": content})

                usage_meta = getattr(chunk, "usage_metadata", None)
                if usage_meta:
                    input_tokens = usage_meta.get("input_tokens") or input_tokens or 0
                    output_tokens = usage_meta.get("output_tokens") or output_tokens or 0
                    total_tokens = usage_meta.get("total_tokens") or total_tokens or 0

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

            if hasattr(chat_model, "model"):
                response_model = chat_model.model
            response_provider = agent.provider.value if hasattr(agent.provider, "value") else agent.provider

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
            if trace_id:
                await self._fail_trace(trace_id, str(e))
            return

        try:
            async with self._session_factory() as db_session:
                message_repo = SQLAlchemyMessageRepository(db_session)
                session_repo = SQLAlchemySessionRepository(db_session)
                trace_repo = SQLAlchemyTraceRepository(db_session)
                trace_event_repo = SQLAlchemyTraceEventRepository(db_session)
                usage_repo: UsageEventRepository = SQLAlchemyUsageEventRepository(db_session)
                outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(db_session)

                message_id = None
                if session:
                    assistant_msg = await self._save_assistant_message(
                        message_repo, session_repo, outbox, session, full_answer or "", usage_info, agent
                    )
                    message_id = assistant_msg.id

                try:
                    await self._record_usage(usage_repo, outbox, input_dto, agent, usage_info)
                except Exception as e:
                    logger.warning("Failed to record usage: %s", e)

                try:
                    await self._complete_trace(
                        trace_repo=trace_repo,
                        trace_event_repo=trace_event_repo,
                        trace_id=trace_id,
                        answer=full_answer or "",
                        usage=usage_info,
                        model=response_model or agent.model,
                        provider=response_provider,
                        latency_ms=llm_latency_ms,
                        message_id=message_id,
                        sources=sources,
                        parsed_output=parsed_output,
                        output_parse_error=output_parse_error,
                        tool_calls=[],
                    )
                except Exception as e:
                    logger.warning("Failed to complete trace: %s", e)

                await db_session.commit()

                total_latency = round((time.monotonic() - started_at) * 1000)

                logger.info("Stream done payload usage debug", extra={
                    "trace_id": str(trace_id),
                    "usage": usage_info.model_dump() if usage_info else None,
                })
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
                }

                yield self._sse_event("done", done_payload)

        except Exception as e:
            logger.exception("Teardown error: %s", e)
            yield self._sse_event("error", {"message": f"Teardown error: {e}"})

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
            from modules.ai.domain.enums import Provider
            agent.provider = Provider(release.provider) if isinstance(release.provider, str) else release.provider
        if release.model is not None:
            agent.model = release.model
        if release.provider_credential_id is not None:
            agent.provider_credential_id = release.provider_credential_id
        if release.temperature is not None:
            agent.temperature = release.temperature
        if release.max_output_tokens is not None:
            agent.max_output_tokens = release.max_output_tokens
        if release.session_mode is not None:
            from modules.ai.domain.enums import SessionMode
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
            from modules.ai.domain.enums import Provider
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
            from modules.ai.domain.enums import SessionMode
            agent.session_mode = SessionMode(snapshot["session_mode"]) if isinstance(snapshot["session_mode"], str) else snapshot["session_mode"]
        return agent

    async def _load_credential(self, repo: ProviderCredentialRepository, agent: Agent) -> ProviderCredential:
        if not agent.provider_credential_id:
            raise ValueError("Agent has no provider credential configured")
        credential = await repo.get_by_id(agent.provider_credential_id)
        if not credential:
            raise CredentialNotFoundError(agent.provider_credential_id)
        return credential

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", credential.id, e)
            raise ValueError("Provider credential secret could not be decrypted. Recreate the credential.")

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        provider_val = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        if provider_val == "custom":
            base_url = (
                (agent.settings or {}).get("base_url")
                or (credential.metadata or {}).get("base_url")
            )
            if not base_url:
                raise ValueError("Custom provider requires base_url in credential metadata or agent settings")
            model = agent.model or (credential.metadata or {}).get("model")
            if not model:
                raise ValueError("Custom provider requires model in agent or credential metadata")
            return base_url
        return None

    async def _resolve_session(
        self, repo: SessionRepository, input_dto: AskInput, agent: Agent
    ) -> Session | None:
        mode = agent.session_mode.value if hasattr(agent.session_mode, "value") else agent.session_mode
        if mode == "stateless":
            return None

        if input_dto.session_id:
            try:
                return await repo.get_by_id(input_dto.session_id)
            except Exception:
                pass

        session = Session(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            external_session_id=None,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            mode=SessionMode.CHAT,
        )
        return await repo.create(session)

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
        )
        created = await message_repo.create(msg)
        session.last_message_at = utc_now()
        try:
            await session_repo.update(session)
        except Exception:
            pass

        await outbox.write(
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

    async def _load_history(self, repo: MessageRepository, session: Session) -> list:
        try:
            messages = await repo.list_by_session(session.id)
            history = []
            for m in messages:
                role = m.role.value if hasattr(m.role, "value") else m.role
                if role == "user":
                    history.append(HumanMessage(content=m.content))
                elif role == "assistant":
                    history.append(AIMessage(content=m.content))
            return history
        except Exception:
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

    async def _create_trace(
        self,
        trace_repo: TraceRepository,
        trace_event_repo: TraceEventRepository,
        input_dto: AskInput,
        agent: Agent,
        session: Session | None,
    ) -> UUID:
        trace = Trace(
            project_id=input_dto.project_id,
            agent_id=agent.id,
            session_id=session.id if session else None,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            status=TraceStatus.running,
            started_at=datetime.now(timezone.utc),
            provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            model=agent.model,
        )
        saved = await trace_repo.save(trace)
        trace_id = saved.id

        try:
            event = TraceEvent(
                trace_id=trace_id,
                project_id=input_dto.project_id,
                event_type=TraceEventType.info,
                payload={"event": "ask.started", "message": input_dto.message[:200]},
            )
            await trace_event_repo.save(event)
        except Exception:
            pass

        return trace_id

    async def _fail_trace(self, trace_id: UUID | None, error: str) -> None:
        if not trace_id:
            return
        try:
            async with self._session_factory() as db_session:
                trace_repo = SQLAlchemyTraceRepository(db_session)
                trace = await trace_repo.get_by_id(trace_id)
                if trace:
                    trace.status = TraceStatus.failed
                    trace.ended_at = datetime.now(timezone.utc)
                    trace.error = error
                    await trace_repo.save(trace)
                await db_session.commit()
        except Exception as e:
            logger.warning("Failed to fail trace %s: %s", trace_id, e)

    async def _complete_trace(
        self,
        trace_repo: TraceRepository,
        trace_event_repo: TraceEventRepository,
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
    ) -> None:
        if not trace_id:
            return
        try:
            trace = await trace_repo.get_by_id(trace_id)
            if trace:
                trace.status = TraceStatus.completed
                trace.ended_at = datetime.now(timezone.utc)
                trace.total_latency_ms = latency_ms
                trace.model = model
                trace.provider = provider
                trace.data = {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": usage.cost_usd,
                    "sources": [s.model_dump() for s in sources] if sources else None,
                    "tool_calls": tool_calls or None,
                    "parsed_output": parsed_output,
                    "output_parse_error": output_parse_error,
                }
                logger.info("Stream trace usage persistence debug", extra={
                    "trace_id": str(trace_id),
                    "data": trace.data,
                })
                await trace_repo.save(trace)

            event = TraceEvent(
                trace_id=trace_id,
                project_id=trace.project_id if trace else uuid.uuid4(),
                event_type=TraceEventType.info,
                latency_ms=latency_ms,
                payload={
                    "event": "ask.completed",
                    "answer_length": len(answer),
                    "message_id": str(message_id) if message_id else None,
                },
            )
            await trace_event_repo.save(event)
        except Exception as e:
            logger.warning("Failed to complete trace %s: %s", trace_id, e)

    async def _record_usage(
        self,
        usage_repo: UsageEventRepository,
        outbox: OutboxEventWriter,
        input_dto: AskInput,
        agent: Agent,
        usage: UsageInfo,
    ) -> None:
        try:
            event = UsageEvent(
                project_id=input_dto.project_id,
                agent_id=agent.id,
                event_type=UsageEventType.llm_request,
                quantity=usage.total_tokens or 0,
                unit=UsageUnit.token,
                cost_usd=usage.cost_usd,
                data={
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "model": agent.model,
                },
            )
            await usage_repo.save(event)

            await outbox.write(
                aggregate_type="UsageEvent",
                aggregate_id=event.id,
                event_type="usage_event.recorded",
                payload={
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(agent.id),
                    "event_type": "llm_request",
                    "quantity": usage.total_tokens or 0,
                },
            )
        except Exception:
            pass
