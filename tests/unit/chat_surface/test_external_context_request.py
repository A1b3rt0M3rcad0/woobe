from uuid import uuid4

from modules.chat_surface.application.dtos import StreamChatMessageRequest
from modules.chat_surface.application.runtime_gateway import ChatRuntimeRequest


def test_stream_chat_message_request_accepts_external_context() -> None:
    payload = StreamChatMessageRequest(
        message="Quero alterar meu plano",
        metadata={"source": "web"},
        external_context={
            "customer_name": "Mariana Costa",
            "plan": "business",
            "current_page": "/billing/subscription",
        },
    )

    assert payload.external_context == {
        "customer_name": "Mariana Costa",
        "plan": "business",
        "current_page": "/billing/subscription",
    }


def test_chat_runtime_request_keeps_external_context_separate_from_metadata() -> None:
    project_id = uuid4()
    target_id = uuid4()
    release_id = uuid4()
    session_id = uuid4()
    surface_id = uuid4()
    message_request_id = uuid4()
    external_context = {
        "customer_name": "Mariana Costa",
        "current_page": "/billing/subscription",
    }

    request = ChatRuntimeRequest(
        project_id=project_id,
        target_type="agent",
        target_id=target_id,
        target_release_id=release_id,
        session_id=session_id,
        surface_id=surface_id,
        message_request_id=message_request_id,
        message="Quero alterar meu plano",
        metadata={"source": "web"},
        external_context=external_context,
        session_source="chat_surface",
        created=True,
    )

    assert request.external_context == external_context
    assert request.metadata == {"source": "web"}
    assert "customer_name" not in request.metadata
