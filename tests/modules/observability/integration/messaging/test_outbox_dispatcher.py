from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "modules" / "observability"
DISPATCHER_FILE = OBSERVABILITY_DIR / "infra" / "workers" / "outbox_dispatcher.py"
EVENT_MAPPERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "event_mappers.py"
PUBLISHERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "publishers.py"


class TestObservabilityOutboxDispatcher:
    def test_dispatcher_file_exists(self):
        assert DISPATCHER_FILE.is_file(), "Outbox dispatcher file must exist"

    def test_dispatcher_class_exists(self):
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityOutboxDispatcherWorker" in content

    def test_dispatcher_extends_base(self):
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

    def test_event_mappers_file_exists(self):
        assert EVENT_MAPPERS_FILE.is_file(), "Event mappers file must exist"

    def test_event_mappers_have_outbox_to_rabbit(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        assert "def outbox_to_rabbit_message" in content

    def test_event_mappers_have_rabbit_to_inbox(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        assert "def rabbit_message_to_inbox" in content

    def test_publishers_file_exists(self):
        assert PUBLISHERS_FILE.is_file(), "Publishers file must exist"

    def test_publisher_class_exists(self):
        content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityRabbitMQPublisher" in content

    def test_publisher_has_publish_method(self):
        content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "async def publish" in content
