from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MESSAGING_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent" / "infra" / "messaging"
EVENT_MAPPERS_FILE = MESSAGING_DIR / "event_mappers.py"
PUBLISHERS_FILE = MESSAGING_DIR / "publishers.py"
CONSUMERS_FILE = MESSAGING_DIR / "consumers.py"
INBOX_HANDLERS_FILE = MESSAGING_DIR / "inbox_handlers.py"

REQUIRED_MESSAGING_FILES = [
    "__init__.py",
    "consumers.py",
    "event_mappers.py",
    "inbox_handlers.py",
    "publishers.py",
]

EXPECTED_EVENT_MAPPER_FUNCTIONS = [
    "domain_event_to_outbox",
    "outbox_to_rabbit_message",
    "rabbit_message_to_inbox",
]

EXPECTED_EVENT_MAPPER_CLASSES = [
    "RabbitMQMessageEnvelope",
]


class TestNormalizeAgentMessagingContracts:
    def test_messaging_directory_exists(self):
        assert MESSAGING_DIR.is_dir()

    def test_all_required_messaging_files_exist(self):
        for name in REQUIRED_MESSAGING_FILES:
            file_path = MESSAGING_DIR / name
            assert file_path.is_file(), f"Missing messaging file: {name}"

    def test_event_mappers_is_populated(self):
        assert EVENT_MAPPERS_FILE.stat().st_size > 5000, "event_mappers.py is too small"

    def test_event_mappers_have_required_functions(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        for func in EXPECTED_EVENT_MAPPER_FUNCTIONS:
            assert f"def {func}" in content, f"event_mappers missing function: {func}"

    def test_event_mappers_have_required_classes(self):
        content = EVENT_MAPPERS_FILE.read_text(encoding="utf-8")
        for cls in EXPECTED_EVENT_MAPPER_CLASSES:
            assert f"class {cls}" in content, f"event_mappers missing class: {cls}"

    def test_publishers_is_populated(self):
        content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        assert "class AgentRabbitMQPublisher" in content, "publishers missing AgentRabbitMQPublisher"
        assert "async def publish" in content, "AgentRabbitMQPublisher missing publish method"

    def test_consumers_is_populated(self):
        content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "class AgentRabbitMQConsumer" in content, "consumers missing AgentRabbitMQConsumer"
        assert "async def consume" in content, "AgentRabbitMQConsumer missing consume method"

    def test_inbox_handlers_is_populated(self):
        content = INBOX_HANDLERS_FILE.read_text(encoding="utf-8")
        assert "class AgentInboxEventRouter" in content, "inbox_handlers missing AgentInboxEventRouter"
        assert "async def handle" in content, "AgentInboxEventRouter missing handle method"
        assert "def register" in content, "AgentInboxEventRouter missing register method"

    def test_no_legacy_imports_in_messaging(self):
        for py_file in MESSAGING_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            legacy_patterns = ["modules.ai", "modules.knowledge", "modules.runtime"]
            for pattern in legacy_patterns:
                assert pattern not in content, \
                    f"{py_file.name} contains legacy import: {pattern}"

    def test_publishers_and_consumers_use_rabbitmq_manager(self):
        pub_content = PUBLISHERS_FILE.read_text(encoding="utf-8")
        con_content = CONSUMERS_FILE.read_text(encoding="utf-8")
        assert "RabbitMQManager" in pub_content, "publishers must reference RabbitMQManager"
        assert "RabbitMQManager" in con_content, "consumers must reference RabbitMQManager"
