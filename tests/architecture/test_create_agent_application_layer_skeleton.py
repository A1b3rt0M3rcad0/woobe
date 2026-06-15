from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
APP_DIR = SRC_DIR / "modules" / "agent" / "application"

EXPECTED_FILES = [
    APP_DIR / "__init__.py",
    APP_DIR / "use_cases" / "__init__.py",
    APP_DIR / "dtos" / "__init__.py",
    APP_DIR / "handlers" / "__init__.py",
    APP_DIR / "composers" / "__init__.py",
]


class TestCreateAgentApplicationLayerSkeleton:
    def test_create_agent_application_layer_skeleton_success(self):
        assert APP_DIR.is_dir(), f"Application directory missing: {APP_DIR}"

        for filepath in EXPECTED_FILES:
            assert filepath.is_file(), f"Application skeleton file missing: {filepath}"

        import importlib

        mod = importlib.import_module("modules.agent.application")
        assert mod is not None

        for name in ["use_cases", "dtos", "handlers", "composers"]:
            sub = importlib.import_module(f"modules.agent.application.{name}")
            assert sub is not None

    def test_create_agent_application_layer_skeleton_rejects_forbidden_dependency(self):
        legacy_imports = [
            "from modules.ai",
            "from modules.knowledge",
            "from modules.runtime",
            "import modules.ai",
            "import modules.knowledge",
            "import modules.runtime",
        ]

        for filepath in EXPECTED_FILES:
            if not filepath.is_file():
                continue
            content = filepath.read_text(encoding="utf-8")
            for forbidden in legacy_imports:
                assert forbidden not in content, (
                    f"Forbidden import '{forbidden}' found in {filepath}"
                )
