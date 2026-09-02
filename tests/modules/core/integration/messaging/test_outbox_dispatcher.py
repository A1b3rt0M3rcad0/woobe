from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_DIR = (
    PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core"
)

EVENT_MAPPERS_FILE = CORE_DIR / "infra" / "messaging" / "event_mappers.py"
PUBLISHERS_FILE = CORE_DIR / "infra" / "messaging" / "publishers.py"
CONSUMERS_FILE = CORE_DIR / "infra" / "messaging" / "consumers.py"
DISPATCHER_FILE = CORE_DIR / "infra" / "workers" / "outbox_dispatcher.py"


class TestCoreOutboxDispatcher:
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

    def test_publishers_has_core_publisher_class(self):
        content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "class CoreRabbitMQPublisher" in content

    def test_consumers_has_core_consumer_class(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "class CoreRabbitMQConsumer" in content

    def test_dispatcher_has_core_dispatcher_class(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "class CoreOutboxDispatcherWorker" in content

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

    def test_dispatcher_uses_core_outbox_model(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "OutboxEventModel" in content
