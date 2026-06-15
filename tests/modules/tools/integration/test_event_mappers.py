from modules.tools.infra.messaging.event_mappers import (
    rabbit_message_to_inbox,
)
from modules.tools.infra.database.models import OutboxEventModel


class TestToolsEventMappers:
    def test_outbox_to_rabbit_message_exists(self):
        from modules.tools.infra.messaging.event_mappers import outbox_to_rabbit_message
        assert callable(outbox_to_rabbit_message)

    def test_rabbit_message_to_inbox_exists(self):
        assert callable(rabbit_message_to_inbox)

    def test_outbox_to_rabbit_message_returns_envelope(self):
        from modules.tools.infra.messaging.event_mappers import outbox_to_rabbit_message
        record = OutboxEventModel(
            event_type="tools.tool.created",
            event_version=1,
            aggregate_type="tool",
            aggregate_id="00000000-0000-0000-0000-000000000001",
            payload={"name": "test"},
        )
        envelope = outbox_to_rabbit_message(record)
        assert envelope.routing_key == "tools.tool.created"
        assert "test" in envelope.body
