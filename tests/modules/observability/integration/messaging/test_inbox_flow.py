from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "modules" / "observability"
CONSUMERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "consumers.py"
INBOX_HANDLERS_FILE = OBSERVABILITY_DIR / "infra" / "messaging" / "inbox_handlers.py"
INBOX_CONSUMER_FILE = OBSERVABILITY_DIR / "infra" / "workers" / "inbox_consumer.py"
INBOX_PROCESSOR_FILE = OBSERVABILITY_DIR / "infra" / "workers" / "inbox_processor.py"
REGISTRY_FILE = OBSERVABILITY_DIR / "infra" / "workers" / "registry.py"


class TestObservabilityInboxFlow:
    def test_consumers_file_exists(self):
        assert CONSUMERS_FILE.is_file(), "Consumers file must exist"

    def test_consumer_class_exists(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityRabbitMQConsumer" in content

    def test_consumer_has_consume(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "async def consume" in content

    def test_inbox_handlers_file_exists(self):
        assert INBOX_HANDLERS_FILE.is_file(), "Inbox handlers file must exist"

    def test_inbox_handlers_class_exists(self):
        content = INBOX_HANDLERS_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityInboxEventRouter" in content

    def test_inbox_handlers_has_handle(self):
        content = INBOX_HANDLERS_FILE.read_text(encoding="utf-8")
        assert "async def handle" in content

    def test_inbox_consumer_file_exists(self):
        assert INBOX_CONSUMER_FILE.is_file(), "Inbox consumer file must exist"

    def test_inbox_consumer_class_exists(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityInboxConsumerWorker" in content

    def test_inbox_processor_file_exists(self):
        assert INBOX_PROCESSOR_FILE.is_file(), "Inbox processor file must exist"

    def test_inbox_processor_class_exists(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityInboxProcessorWorker" in content

    def test_registry_file_exists(self):
        assert REGISTRY_FILE.is_file(), "Registry file must exist"

    def test_registry_class_exists(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityWorkerRegistry" in content

    def test_registry_has_register_observability_workers(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "def register_observability_workers" in content

    def test_inbox_event_router_handles_events(self):
        content = INBOX_HANDLERS_FILE.read_text(encoding="utf-8")
        assert "observability.trace.started.v1" in content
        assert "observability.trace.completed.v1" in content
        assert "observability.trace.failed.v1" in content

    def test_consumer_no_import_cross_module(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "modules.agent" not in content
        assert "modules.ai" not in content
        assert "modules.knowledge" not in content
        assert "modules.runtime" not in content
