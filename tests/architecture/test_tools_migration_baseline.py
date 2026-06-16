from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "src" / "modules" / "tools"
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"

EXPECTED_TOOLS_LAYERS = [
    "domain",
    "application",
    "application/dtos",
    "application/use_cases",
    "application/composers",
    "infra/database",
    "infra/messaging",
    "infra/workers",
    "presentation",
    "presentation/controllers",
]

EXPECTED_TOOLS_DOMAIN_FILES = [
    "entities.py",
    "enums.py",
    "errors.py",
    "events.py",
    "repositories.py",
    "services.py",
    "value_objects.py",
]


class TestToolsBaseline:
    def test_tools_module_exists(self):
        assert TOOLS_DIR.is_dir()

    def test_tools_module_has_expected_layers(self):
        for layer in EXPECTED_TOOLS_LAYERS:
            layer_path = TOOLS_DIR / layer
            assert layer_path.is_dir(), f"Missing layer: {layer}"

    def test_tools_domain_has_expected_files(self):
        for fname in EXPECTED_TOOLS_DOMAIN_FILES:
            fpath = TOOLS_DIR / "domain" / fname
            assert fpath.is_file(), f"Missing domain file: {fname}"

    def test_tools_database_has_expected_files(self):
        db_dir = TOOLS_DIR / "infra" / "database"
        for fname in ("models.py", "mappers.py", "repositories.py", "unit_of_work.py"):
            assert (db_dir / fname).is_file(), f"Missing database file: {fname}"

    def test_tools_has_own_uow(self):
        uow_path = TOOLS_DIR / "infra" / "database" / "unit_of_work.py"
        content = uow_path.read_text(encoding="utf-8")
        assert "class ToolsUnitOfWork" in content

    def test_tools_has_own_schema(self):
        models_path = TOOLS_DIR / "infra" / "database" / "models.py"
        content = models_path.read_text(encoding="utf-8")
        assert '"tools"' in content or "'tools'" in content

    def test_agent_has_tool_ports(self):
        port_dir = AGENT_DIR / "domain" / "ports"
        assert (port_dir / "tool_executor.py").is_file()
        assert (port_dir / "tool_repository.py").is_file()

    def test_agent_has_tool_adapters(self):
        adapter_dir = AGENT_DIR / "infra" / "adapters"
        assert (adapter_dir / "tools_tool_executor.py").is_file()
        assert (adapter_dir / "tools_tool_repository.py").is_file()

    def test_agent_uow_does_not_have_tool_repos_yet(self):
        uow_path = AGENT_DIR / "infra" / "database" / "unit_of_work.py"
        content = uow_path.read_text(encoding="utf-8")
        assert "SQLAlchemyToolRepository" not in content
        assert "SQLAlchemySecretRepository" not in content
