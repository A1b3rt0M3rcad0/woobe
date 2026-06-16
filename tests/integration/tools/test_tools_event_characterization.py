from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLS_USE_CASES = PROJECT_ROOT / "src" / "modules" / "tools" / "application" / "use_cases" / "tools_use_cases.py"
TOOLS_EVENTS = PROJECT_ROOT / "src" / "modules" / "tools" / "domain" / "events.py"
TOOLS_MODELS = PROJECT_ROOT / "src" / "modules" / "tools" / "infra" / "database" / "models.py"
TOOLS_INBOX_HANDLERS = PROJECT_ROOT / "src" / "modules" / "tools" / "infra" / "messaging" / "inbox_handlers.py"

EXPECTED_EVENT_TYPES = [
    "tools.tool.created",
    "tools.tool.updated",
    "tools.tool.status_changed",
    "tools.secret.created",
]


class TestToolsEventCharacterization:
    def test_events_module_exists(self):
        assert TOOLS_EVENTS.is_file()

    def test_outbox_model_exists(self):
        content = TOOLS_MODELS.read_text(encoding="utf-8")
        assert "OutboxEventModel" in content

    def test_inbox_model_exists(self):
        content = TOOLS_MODELS.read_text(encoding="utf-8")
        assert "InboxEventModel" in content

    def test_tool_created_event_in_use_cases(self):
        content = TOOLS_USE_CASES.read_text(encoding="utf-8")
        assert "tools.tool.created" in content

    def test_tool_updated_event_in_use_cases(self):
        content = TOOLS_USE_CASES.read_text(encoding="utf-8")
        assert "tools.tool.updated" in content

    def test_tool_status_changed_event_in_use_cases(self):
        content = TOOLS_USE_CASES.read_text(encoding="utf-8")
        assert "tools.tool.status_changed" in content

    def test_secret_created_event_in_use_cases(self):
        content = TOOLS_USE_CASES.read_text(encoding="utf-8")
        assert "tools.secret.created" in content

    def test_inbox_handler_has_handled_events(self):
        content = TOOLS_INBOX_HANDLERS.read_text(encoding="utf-8")
        for evt in EXPECTED_EVENT_TYPES:
            assert evt in content, f"Missing handler for event: {evt}"

    def test_event_mapper_exists(self):
        mapper_path = PROJECT_ROOT / "src" / "modules" / "tools" / "infra" / "messaging" / "event_mappers.py"
        assert mapper_path.is_file()
