from uuid import uuid4

from modules.metering.domain.entities import UsageEvent


def test_usage_event_derives_network_dimensions_from_payload() -> None:
    network_id = uuid4()
    execution_id = uuid4()
    version_id = uuid4()

    event = UsageEvent(
        data={
            "network_id": str(network_id),
            "network_execution_id": str(execution_id),
            "network_version_id": str(version_id),
        }
    )

    assert event.network_id == network_id
    assert event.network_execution_id == execution_id
    assert event.network_version_id == version_id


def test_agent_execution_id_is_not_used_as_network_execution_id() -> None:
    event = UsageEvent(
        data={
            "network_id": str(uuid4()),
            "execution_id": str(uuid4()),
        }
    )

    assert event.network_id is not None
    assert event.network_execution_id is None
