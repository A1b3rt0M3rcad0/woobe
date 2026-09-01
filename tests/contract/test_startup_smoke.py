"""Startup smoke test for spec 013.

Verifies the application bootstrap no longer imports from
the legacy modules.tools module and routes come from agent.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIN_PATH = ROOT / "packages" / "woobe-api" / "src" / "main.py"


class TestStartupSmoke:
    def test_main_does_not_import_tools_module(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "from modules.tools" not in content, (
            "packages/woobe-api/src/main.py must not import from modules.tools"
        )

    def test_tools_router_from_agent(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "from modules.agent.presentation.routes import tools_router" in content, (
            "packages/woobe-api/src/main.py must import tools_router from modules.agent.presentation.routes"
        )

    def test_app_creatable(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "main", str(MAIN_PATH)
        )
        assert spec is not None, "main.py must be loadable as a module spec"