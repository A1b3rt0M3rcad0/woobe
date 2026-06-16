from modules.metering.infra.messaging.event_mappers import (
    rabbit_message_to_inbox,
)
from modules.metering.infra.database.models import OutboxEventModel


class TestMeteringEventMappers:
    def test_outbox_to_rabbit_message_exists(self):
        from modules.metering.infra.messaging.event_mappers import outbox_to_rabbit_message
        assert callable(outbox_to_rabbit_message)

    def test_rabbit_message_to_inbox_exists(self):
        assert callable(rabbit_message_to_inbox)

    def test_outbox_to_rabbit_message_returns_envelope(self):
        from modules.metering.infra.messaging.event_mappers import outbox_to_rabbit_message
        record = OutboxEventModel(
            event_type="metering.usage.recorded.v1",
            event_version=1,
            aggregate_type="usage_event",
            aggregate_id="00000000-0000-0000-0000-000000000001",
            payload={"project_id": "00000000-0000-0000-0000-000000000002"},
        )
        envelope = outbox_to_rabbit_message(record)
        assert envelope.routing_key == "metering.usage.recorded.v1"
        assert "project_id" in envelope.body
