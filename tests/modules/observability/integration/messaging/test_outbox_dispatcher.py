from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
)
DISPATCHER_FILE = OBSERVABILITY_DIR / "infra" / "workers" / "outbox_dispatcher.py"
EVENT_MAPPERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "event_mappers.py"
PUBLISHERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "publishers.py"


class TestObservabilityOutboxDispatcher:
    def test_dispatcher_structure(self):
        assert DISPATCHER_FILE.is_file()
        content = DISPATCHER_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityOutboxDispatcherWorker" in content
        assert "BaseOutboxDispatcher" in content
        assert "async def claim_pending" in content
        assert "async def publish" in content
        assert "async def mark_published" in content
        assert "async def mark_failed" in content
        assert "AsyncSession(" not in content
        assert "ObservabilityUnitOfWork" in content

    def test_messaging_adapters_exist(self):
        assert EVENT_MAPPERS_FILE.is_file()
        mapper_source = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        assert "def outbox_to_rabbit_message" in mapper_source
        assert "def rabbit_message_to_inbox" in mapper_source
        assert PUBLISHERS_FILE.is_file()
        publisher_source = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityRabbitMQPublisher" in publisher_source
        assert "async def publish" in publisher_source
