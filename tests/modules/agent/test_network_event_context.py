from uuid import uuid4

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.events import AgentExecutionStartedV1
from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox


def test_agent_execution_event_inherits_active_network_context() -> None:
    context = new_execution_context()
    context.network_id = uuid4()
    context.network_execution_id = uuid4()
    context.network_session_id = uuid4()
    context.network_version_id = uuid4()
    token = current_execution.set(context)
    try:
        event = AgentExecutionStartedV1.create(
            agent_id=uuid4(),
            session_id=uuid4(),
            payload={"trace_id": str(uuid4()), "model": "test"},
        )
        outbox = domain_event_to_outbox(event)
    finally:
        current_execution.reset(token)

    assert outbox.payload["network_id"] == str(context.network_id)
    assert outbox.payload["network_execution_id"] == str(context.network_execution_id)
    assert outbox.payload["network_session_id"] == str(context.network_session_id)
    assert outbox.payload["network_version_id"] == str(context.network_version_id)
