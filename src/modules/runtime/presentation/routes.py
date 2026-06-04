from fastapi import APIRouter, Request as FastAPIRequest

from modules.runtime.application.composers.ask_agent_composer import ask_agent_composer
from modules.runtime.application.composers.create_session_composer import create_session_composer
from modules.runtime.application.composers.list_messages_composer import list_messages_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.post("/sessions")
async def create_session(request: FastAPIRequest):
    handler = create_session_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/ask")
async def ask(request: FastAPIRequest):
    handler = ask_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/sessions/{session_id}/messages")
async def list_messages(request: FastAPIRequest):
    handler = list_messages_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
