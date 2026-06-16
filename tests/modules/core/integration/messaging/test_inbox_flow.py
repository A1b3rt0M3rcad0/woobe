from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_DIR = PROJECT_ROOT / "src" / "modules" / "core"

INBOX_CONSUMER_FILE = CORE_DIR / "infra" / "workers" / "inbox_consumer.py"
INBOX_PROCESSOR_FILE = CORE_DIR / "infra" / "workers" / "inbox_processor.py"
INBOX_HANDLERS_FILE = CORE_DIR / "infra" / "messaging" / "inbox_handlers.py"
REGISTRY_FILE = CORE_DIR / "infra" / "workers" / "registry.py"


class TestCoreInboxFlow:
    def test_inbox_consumer_file_exists(self):
        assert INBOX_CONSUMER_FILE.is_file()

    def test_inbox_processor_file_exists(self):
        assert INBOX_PROCESSOR_FILE.is_file()

    def test_inbox_handlers_file_exists(self):
        assert INBOX_HANDLERS_FILE.is_file()

    def test_registry_file_exists(self):
        assert REGISTRY_FILE.is_file()

    def test_inbox_consumer_has_core_class(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "class CoreInboxConsumerWorker" in content

    def test_inbox_consumer_extends_base_inbox_consumer(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "BaseInboxConsumer" in content

    def test_inbox_consumer_has_consume_method(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "async def consume" in content

    def test_inbox_consumer_has_inbox_queue_defined(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "CORE_INBOX_QUEUE" in content

    def test_inbox_processor_has_core_class(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "class CoreInboxProcessorWorker" in content

    def test_inbox_processor_extends_base_inbox_processor(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "BaseInboxProcessor" in content

    def test_inbox_processor_has_claim_pending(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "async def claim_pending" in content

    def test_inbox_processor_has_process(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "async def process" in content

    def test_registry_has_register_function(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "def register_core_workers" in content

    def test_registry_registers_three_workers(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "CoreOutboxDispatcherWorker" in content
        assert "CoreInboxConsumerWorker" in content
        assert "CoreInboxProcessorWorker" in content

    def test_registry_has_worker_registry_class(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "class CoreWorkerRegistry" in content
