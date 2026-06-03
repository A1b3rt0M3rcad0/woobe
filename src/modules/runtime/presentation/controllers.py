from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from modules.runtime.application.providers import (
    provide_create_session_uc,
    provide_list_messages,
    provide_send_message_uc,
)
from modules.runtime.presentation.schemas import (
    AskResponse,
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionResponse,
)
from modules.runtime.service.dtos import CreateSessionInput, SendMessageInput
from shared.domain.errors import NotFoundError, ValidationError
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, error, ok

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_create_session_uc(manager.session)
        dto = CreateSessionInput(
            project_id=body.project_id,
            agent_id=body.agent_id,
            external_session_id=body.external_session_id,
            tenant_id=body.tenant_id,
            user_id=body.user_id,
            mode=body.mode,
        )
        result = await uc.execute(dto)
        return created(
            SessionResponse(
                id=result.id,
                project_id=result.project_id,
                agent_id=result.agent_id,
                external_session_id=result.external_session_id,
                tenant_id=result.tenant_id,
                user_id=result.user_id,
                status=result.status,
                mode=result.mode,
                data=result.data,
                last_message_at=result.last_message_at,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )
    except ValidationError as e:
        return error(str(e), status_code=422)


@router.post("/ask")
async def ask(
    body: SendMessageRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_send_message_uc(manager.session)
        dto = SendMessageInput(
            session_id=body.session_id,
            content=body.content,
        )
        result = await uc.execute(dto)
        return ok(
            AskResponse(
                answer=result.message.content,
                session_id=result.session_id,
                message_id=result.message.id,
                usage={
                    "input_tokens": result.message.input_tokens,
                    "output_tokens": result.message.output_tokens,
                    "cost_usd": result.message.cost_usd,
                },
            )
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)
    except ValidationError as e:
        return error(str(e), status_code=422)


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    manager=Depends(get_session_manager),
):
    try:
        messages = await provide_list_messages(manager.session, session_id, offset, limit)
        return ok(
            [
                MessageResponse(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    input_tokens=m.input_tokens,
                    output_tokens=m.output_tokens,
                    cost_usd=m.cost_usd,
                    data=m.data,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in messages
            ]
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)
