from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.errors import AgentNotFoundError, CredentialNotFoundError
from modules.ai.domain.repositories import (
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.infra.llm.langchain_factory import create_chat_model
from modules.knowledge.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
)
from modules.metering.domain.entities import UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.domain.repositories import UsageEventRepository
from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.domain.repositories import (
    TraceEventRepository,
    TraceRepository,
)
from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.enums import MessageRole, SessionMode
from modules.runtime.domain.repositories import MessageRepository, SessionRepository
from modules.runtime.service.dtos import (
    AskInput,
    AskOutput,
    SourceInfo,
    UsageInfo,
)
from shared.domain.events import OutboxEventWriter
from shared.domain.time import utc_now
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret

logger = logging.getLogger(__name__)


class AskAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        agent_collection_repo: AgentCollectionRepository,
        chunk_repo: DocumentChunkRepository,
        trace_repo: TraceRepository,
        trace_event_repo: TraceEventRepository,
        usage_repo: UsageEventRepository,
        outbox: OutboxEventWriter,
        encryption_key: str | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._agent_collection_repo = agent_collection_repo
        self._chunk_repo = chunk_repo
        self._trace_repo = trace_repo
        self._trace_event_repo = trace_event_repo
        self._usage_repo = usage_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(self, input_dto: AskInput) -> AskOutput:
        started_at = time.monotonic()
        trace_id: UUID | None = None

        agent = await self._load_agent(input_dto.project_id, input_dto.agent_id)

        credential = await self._load_credential(agent)
        api_key = self._decrypt_api_key(credential)
        base_url = self._resolve_base_url(agent, credential)

        response_format = self._get_response_format(agent)
        json_enabled = (
            response_format.get("enabled", False)
            and response_format.get("type") == "json"
        )

        chat_model = create_chat_model(
            provider=agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            model=agent.model,
            api_key=api_key,
            base_url=base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if json_enabled else None,
        )

        session = await self._resolve_session(input_dto, agent)

        if session:
            await self._save_user_message(session, input_dto.message, agent)

        trace_id = await self._create_trace(input_dto, agent, session)

        history = await self._load_history(session) if session else []

        rag_context, sources = await self._load_rag_context(agent, input_dto.message)

        messages = self._build_messages(agent, rag_context, history, input_dto.message, response_format if json_enabled else None)

        try:
            llm_latency_start = time.monotonic()
            result = await chat_model.ainvoke(messages)
            llm_latency_ms = round((time.monotonic() - llm_latency_start) * 1000)
        except Exception as e:
            await self._fail_trace(trace_id, str(e))
            raise ValueError(f"AI provider error: {e}") from e

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

        usage_meta = getattr(result, "usage_metadata", None) or {}
        usage = UsageInfo(
            input_tokens=usage_meta.get("input_tokens"),
            output_tokens=usage_meta.get("output_tokens"),
            total_tokens=usage_meta.get("total_tokens"),
            cost_usd=None,
        )

        response_meta = getattr(result, "response_metadata", None) or {}
        response_model = response_meta.get("model", agent.model)
        response_provider = response_meta.get("provider", agent.provider.value if hasattr(agent.provider, "value") else agent.provider)

        message_id = None
        if session:
            assistant_msg = await self._save_assistant_message(
                session, answer, usage, agent
            )
            message_id = assistant_msg.id

        try:
            await self._record_usage(input_dto, agent, usage)
        except Exception as e:
            logger.warning("Failed to record usage: %s", e)

        try:
            await self._complete_trace(
                trace_id=trace_id,
                answer=answer,
                usage=usage,
                model=response_model,
                provider=response_provider,
                latency_ms=llm_latency_ms,
                message_id=message_id,
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
            tool_calls=[],
            trace_id=trace_id,
            model=response_model,
            provider=response_provider,
            fallback_used=False,
            latency_ms=total_latency,
            parsed_output=parsed_output,
            output_parse_error=output_parse_error,
        )

    async def _load_agent(self, project_id: UUID, agent_id: UUID) -> Agent:
        agent = await self._agent_repo.get_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        if agent.project_id != project_id:
            raise AgentNotFoundError(agent_id)
        if hasattr(agent, "status") and agent.status and hasattr(agent.status, "value") and agent.status.value != "active":
            from shared.domain.errors import ValidationError
            raise ValidationError(f"Agent {agent_id} is not active")
        return agent

    async def _load_credential(self, agent: Agent) -> ProviderCredential:
        if not agent.provider_credential_id:
            from shared.domain.errors import ValidationError
            raise ValidationError(
                "Agent has no provider credential configured"
            )
        credential = await self._credential_repo.get_by_id(agent.provider_credential_id)
        if not credential:
            raise CredentialNotFoundError(agent.provider_credential_id)
        return credential

    def _decrypt_api_key(self, credential: ProviderCredential) -> str:
        try:
            return decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as e:
            logger.error("Failed to decrypt credential %s: %s", credential.id, e)
            from shared.domain.errors import ValidationError
            raise ValidationError(
                "Provider credential secret could not be decrypted. Recreate the credential."
            )

    def _resolve_base_url(self, agent: Agent, credential: ProviderCredential) -> str | None:
        provider_val = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        if provider_val == "custom":
            base_url = (
                (agent.settings or {}).get("base_url")
                or (credential.metadata or {}).get("base_url")
            )
            if not base_url:
                from shared.domain.errors import ValidationError
                raise ValidationError(
                    "Custom provider requires base_url in credential metadata or agent settings"
                )
            model = agent.model or (credential.metadata or {}).get("model")
            if not model:
                from shared.domain.errors import ValidationError
                raise ValidationError(
                    "Custom provider requires model in agent or credential metadata"
                )
            return base_url
        return None

    async def _resolve_session(
        self, input_dto: AskInput, agent: Agent
    ) -> Session | None:
        mode = agent.session_mode.value if hasattr(agent.session_mode, "value") else agent.session_mode
        if mode == "stateless":
            return None

        if input_dto.session_id:
            try:
                return await self._session_repo.get_by_id(input_dto.session_id)
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
        return await self._session_repo.create(session)

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
        self, session: Session, content: str, usage: UsageInfo, agent: Agent
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

    async def _load_history(self, session: Session) -> list:
        try:
            messages = await self._message_repo.list_by_session(session.id)
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
        saved = await self._trace_repo.save(trace)
        trace_id = saved.id

        try:
            event = TraceEvent(
                trace_id=trace_id,
                project_id=input_dto.project_id,
                event_type=TraceEventType.info,
                payload={"event": "ask.started", "message": input_dto.message[:200]},
            )
            await self._trace_event_repo.save(event)
        except Exception:
            pass

        return trace_id

    async def _fail_trace(self, trace_id: UUID | None, error: str) -> None:
        if not trace_id:
            return
        try:
            trace = await self._trace_repo.get_by_id(trace_id)
            if trace:
                trace.status = TraceStatus.failed
                trace.ended_at = datetime.now(timezone.utc)
                trace.error = error
                await self._trace_repo.save(trace)
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
    ) -> None:
        if not trace_id:
            return
        try:
            trace = await self._trace_repo.get_by_id(trace_id)
            if trace:
                trace.status = TraceStatus.completed
                trace.ended_at = datetime.now(timezone.utc)
                trace.total_latency_ms = latency_ms
                trace.model = model
                trace.provider = provider
                await self._trace_repo.save(trace)

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
            await self._trace_event_repo.save(event)
        except Exception as e:
            logger.warning("Failed to complete trace %s: %s", trace_id, e)

    async def _record_usage(
        self, input_dto: AskInput, agent: Agent, usage: UsageInfo
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
            await self._usage_repo.save(event)

            await self._outbox.write(
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
