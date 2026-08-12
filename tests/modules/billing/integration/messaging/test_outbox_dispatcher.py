from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
BILLING_DIR = PROJECT_ROOT / "src" / "editions" / "cloud" / "billing"

EVENT_MAPPERS_FILE = BILLING_DIR / "infra" / "messaging" / "event_mappers.py"
PUBLISHERS_FILE = BILLING_DIR / "infra" / "messaging" / "publishers.py"
CONSUMERS_FILE = BILLING_DIR / "infra" / "messaging" / "consumers.py"
DISPATCHER_FILE = BILLING_DIR / "infra" / "workers" / "outbox_dispatcher.py"


class TestBillingOutboxDispatcher:
    def test_event_mappers_file_exists(self):
        assert EVENT_MAPPERS_FILE.is_file()

    def test_publishers_file_exists(self):
        assert PUBLISHERS_FILE.is_file()

    def test_consumers_file_exists(self):
        assert CONSUMERS_FILE.is_file()

    def test_dispatcher_file_exists(self):
        assert DISPATCHER_FILE.is_file()

    def test_event_mappers_has_outbox_to_rabbit_message(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        assert "def outbox_to_rabbit_message" in content

    def test_event_mappers_has_rabbit_message_to_inbox(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        assert "def rabbit_message_to_inbox" in content

    def test_publishers_has_billing_publisher_class(self):
        content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "class BillingRabbitMQPublisher" in content

    def test_consumers_has_billing_consumer_class(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "class BillingRabbitMQConsumer" in content

    def test_dispatcher_has_billing_dispatcher_class(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "class BillingOutboxDispatcherWorker" in content

    def test_dispatcher_extends_base_outbox_dispatcher(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "BaseOutboxDispatcher" in content

    def test_dispatcher_has_claim_pending(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "async def claim_pending" in content

    def test_dispatcher_has_publish(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "async def publish" in content

    def test_dispatcher_has_mark_published(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "async def mark_published" in content

    def test_dispatcher_has_mark_failed(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "async def mark_failed" in content

    def test_dispatcher_uses_billing_outbox_model(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "OutboxEventModel" in content
