"""Regression tests for repeatable agent mutation outbox events."""

import uuid6

from modules.agent.domain.events import (
    AgentProviderCredentialUpdatedV1,
    AgentToolStatusChangedV1,
    AgentToolUpdatedV1,
    AgentUpdatedV1,
)
from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox


def test_distinct_agent_updates_receive_distinct_outbox_keys() -> None:
    agent_id = uuid6.uuid7()
    project_id = uuid6.uuid7()

    first = AgentUpdatedV1.create(
        agent_id=agent_id,
        project_id=project_id,
        name="Agent v1",
        provider="custom",
        model="model-a",
    )
    second = AgentUpdatedV1.create(
        agent_id=agent_id,
        project_id=project_id,
        name="Agent v2",
        provider="custom",
        model="model-b",
    )

    assert first.idempotency_key == second.idempotency_key
    assert domain_event_to_outbox(first).idempotency_key != domain_event_to_outbox(second).idempotency_key


def test_mapping_same_mutation_event_remains_deterministic() -> None:
    event = AgentUpdatedV1.create(
        agent_id=uuid6.uuid7(),
        project_id=uuid6.uuid7(),
        name="Agent",
        provider="custom",
        model="model-a",
    )

    first = domain_event_to_outbox(event)
    second = domain_event_to_outbox(event)

    assert first.idempotency_key == second.idempotency_key


def test_request_id_can_deduplicate_recreated_mutation_event() -> None:
    agent_id = uuid6.uuid7()
    project_id = uuid6.uuid7()
    request_id = str(uuid6.uuid7())

    first = AgentUpdatedV1.create(
        agent_id=agent_id,
        project_id=project_id,
        name="Agent",
        provider="custom",
        model="model-a",
        payload={"request_id": request_id},
    )
    second = AgentUpdatedV1.create(
        agent_id=agent_id,
        project_id=project_id,
        name="Agent",
        provider="custom",
        model="model-a",
        payload={"request_id": request_id},
    )

    assert domain_event_to_outbox(first).idempotency_key == domain_event_to_outbox(second).idempotency_key


def test_other_repeatable_mutations_are_scoped_by_occurrence() -> None:
    project_id = uuid6.uuid7()
    tool_id = uuid6.uuid7()
    credential_id = uuid6.uuid7()

    tool_update_a = AgentToolUpdatedV1.create(tool_id=tool_id, payload={"name": "A"})
    tool_update_b = AgentToolUpdatedV1.create(tool_id=tool_id, payload={"name": "B"})
    status_a = AgentToolStatusChangedV1.create(tool_id=tool_id, status="active")
    status_b = AgentToolStatusChangedV1.create(tool_id=tool_id, status="disabled")
    credential_a = AgentProviderCredentialUpdatedV1.create(
        credential_id=credential_id,
        project_id=project_id,
        provider="custom",
        name="Credential A",
    )
    credential_b = AgentProviderCredentialUpdatedV1.create(
        credential_id=credential_id,
        project_id=project_id,
        provider="custom",
        name="Credential B",
    )

    pairs = [
        (tool_update_a, tool_update_b),
        (status_a, status_b),
        (credential_a, credential_b),
    ]
    for first, second in pairs:
        assert domain_event_to_outbox(first).idempotency_key != domain_event_to_outbox(second).idempotency_key
