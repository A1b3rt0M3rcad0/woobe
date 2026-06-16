from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_DIR = PROJECT_ROOT / "src" / "modules" / "identity"

INBOX_CONSUMER_FILE = IDENTITY_DIR / "infra" / "workers" / "inbox_consumer.py"
INBOX_PROCESSOR_FILE = IDENTITY_DIR / "infra" / "workers" / "inbox_processor.py"
INBOX_HANDLERS_FILE = IDENTITY_DIR / "infra" / "messaging" / "inbox_handlers.py"
REGISTRY_FILE = IDENTITY_DIR / "infra" / "workers" / "registry.py"


class TestIdentityInboxFlow:
    def test_inbox_consumer_file_exists(self):
        assert INBOX_CONSUMER_FILE.is_file()

    def test_inbox_processor_file_exists(self):
        assert INBOX_PROCESSOR_FILE.is_file()

    def test_inbox_handlers_file_exists(self):
        assert INBOX_HANDLERS_FILE.is_file()

    def test_registry_file_exists(self):
        assert REGISTRY_FILE.is_file()

    def test_inbox_consumer_has_identity_class(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "class IdentityInboxConsumerWorker" in content

    def test_inbox_consumer_extends_base_inbox_consumer(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "BaseInboxConsumer" in content

    def test_inbox_consumer_has_consume_method(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "async def consume" in content

    def test_inbox_consumer_has_inbox_queue_defined(self):
        content = INBOX_CONSUMER_FILE.read_text(encoding="utf-8")
        assert "IDENTITY_INBOX_QUEUE" in content

    def test_inbox_processor_has_identity_class(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "class IdentityInboxProcessorWorker" in content

    def test_inbox_processor_extends_base_inbox_processor(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "BaseInboxProcessor" in content

    def test_inbox_processor_has_claim_pending(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "async def claim_pending" in content

    def test_inbox_processor_has_process(self):
        content = INBOX_PROCESSOR_FILE.read_text(encoding="utf-8")
        assert "async def process" in content

    def test_registry_has_register_identity_workers(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "def register_identity_workers" in content

    def test_registry_registers_three_workers(self):
        content = REGISTRY_FILE.read_text(encoding="utf-8")
        assert "outbox_dispatcher" in content
        assert "inbox_consumer" in content
        assert "inbox_processor" in content

    def test_inbox_handlers_has_router_class(self):
        content = INBOX_HANDLERS_FILE.read_text(encoding="utf-8")
        assert "class IdentityInboxEventRouter" in content
