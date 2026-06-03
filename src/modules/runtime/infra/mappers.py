from __future__ import annotations

from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus
from modules.runtime.infra.models import MessageModel, SessionModel


def session_to_model(entity: Session) -> SessionModel:
    return SessionModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        external_session_id=entity.external_session_id,
        tenant_id=entity.tenant_id,
        user_id=entity.user_id,
        status=entity.status.value if isinstance(entity.status, SessionStatus) else entity.status,
        data=entity.data,
        last_message_at=entity.last_message_at,
    )


def model_to_session(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        external_session_id=model.external_session_id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        status=SessionStatus(model.status),
        data=model.data,
        last_message_at=model.last_message_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def message_to_model(entity: Message) -> MessageModel:
    return MessageModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        session_id=entity.session_id,
        role=entity.role.value if isinstance(entity.role, MessageRole) else entity.role,
        content=entity.content,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        cost_usd=entity.cost_usd,
        data=entity.data,
    )


def model_to_message(model: MessageModel) -> Message:
    return Message(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        session_id=model.session_id,
        role=MessageRole(model.role),
        content=model.content,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        cost_usd=float(model.cost_usd) if model.cost_usd is not None else None,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )

