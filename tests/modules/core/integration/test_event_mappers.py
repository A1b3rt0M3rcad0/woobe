import json
from uuid import uuid4
from unittest.mock import MagicMock

from modules.core.infra.messaging.event_mappers import (
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
    RabbitMQMessageEnvelope,
)


class FakeOutboxModel:
    def __init__(self):
        self.id = uuid4()
        self.aggregate_type = "project"
        self.aggregate_id = uuid4()
        self.event_type = "core.project.created.v1"
        self.event_version = 1
        self.payload = {"name": "test-project"}
        self.correlation_id = uuid4()
        self.causation_id = uuid4()


class TestOutboxToRabbitMessage:
    def test_returns_envelope(self):
        model = FakeOutboxModel()
        envelope = outbox_to_rabbit_message(model)
        assert isinstance(envelope, RabbitMQMessageEnvelope)
        assert envelope.routing_key
        assert envelope.body


class TestRabbitMessageToInbox:
    def test_creates_inbox_model(self):
        fake_msg = MagicMock()
        payload = {
            "event_type": "core.project.created.v1",
            "event_version": 1,
            "aggregate_type": "project",
            "aggregate_id": str(uuid4()),
            "payload": {"name": "test-project"},
        }
        fake_msg.body = json.dumps(payload).encode()
        inbox = rabbit_message_to_inbox(fake_msg)
        assert inbox.event_type == "core.project.created.v1"
        assert inbox.payload == {"name": "test-project"}
