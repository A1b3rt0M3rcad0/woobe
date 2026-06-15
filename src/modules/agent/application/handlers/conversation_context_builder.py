from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.handlers.conversation_history_mapper import (
    load_and_convert_history,
)
from modules.agent.application.handlers.session_resolver import SessionResolver
from modules.agent.domain.entities import Agent, Message, Session
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.repositories import MessageRepository, SessionRepository
from shared.infra.time import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    session: Session | None = None
    history: list = field(default_factory=list)
    prompt_messages: list = field(default_factory=list)
    user_message_id: UUID | None = None
    history_message_count: int = 0
    history_truncated: bool = False


class ConversationContextBuilder:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._session_repo = session_repo
        self._session_resolver = SessionResolver(session_repo)
        self._message_repo = message_repo

    async def build(
        self,
        input_dto: AskInput,
        agent: Agent,
        rag_context: str | None = None,
        response_format: dict | None = None,
    ) -> ConversationContext:
        mode = agent.session_mode.value if hasattr(agent.session_mode, "value") else agent.session_mode
        session = await self._session_resolver.resolve(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            session_id=input_dto.session_id,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            session_mode=mode,
        )

        history_limit = _get_history_limit(agent)
        history: list = []
        if session:
            history = await load_and_convert_history(
                self._message_repo, session.id, session.id, limit=history_limit,
            )

        user_message_id: UUID | None = None
        if session:
            user_msg = await self._save_user_message(session, agent, input_dto.message)
            user_message_id = user_msg.id

        prompt_messages = build_prompt_messages(agent, rag_context, history, input_dto.message, response_format)

        return ConversationContext(
            session=session,
            history=history,
            prompt_messages=prompt_messages,
            user_message_id=user_message_id,
            history_message_count=len(history),
            history_truncated=session is not None and len(history) < history_limit,
        )

    async def _save_user_message(
        self, session: Session, agent: Agent, content: str,
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


def _get_history_limit(agent: Agent) -> int:
    default = 100
    if not agent.settings:
        return default
    try:
        limit = int(agent.settings.get("history_max_messages", default))
        return max(10, min(limit, 500))
    except (ValueError, TypeError):
        return default


def build_prompt_messages(
    agent: Agent,
    rag_context: str | None,
    history: list,
    user_message: str,
    response_format: dict | None = None,
) -> list:
    messages: list = []
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
