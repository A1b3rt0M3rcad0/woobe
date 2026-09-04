from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
PRESENTATION_DIR = SRC_DIR / "modules" / "agent" / "presentation"

EXPECTED_FILES = [
    PRESENTATION_DIR / "__init__.py",
    PRESENTATION_DIR / "controllers" / "__init__.py",
    PRESENTATION_DIR / "routes.py",
    PRESENTATION_DIR / "schemas.py",
    PRESENTATION_DIR / "mappers.py",
]


class TestCreateAgentPresentationLayerSkeleton:
    def test_create_agent_presentation_layer_skeleton_success(self):
        assert PRESENTATION_DIR.is_dir(), (
            f"Presentation directory missing: {PRESENTATION_DIR}"
        )

        for filepath in EXPECTED_FILES:
            assert filepath.is_file(), (
                f"Presentation skeleton file missing: {filepath}"
            )

        import importlib

        mod = importlib.import_module("modules.agent.presentation")
        assert mod is not None

        for name in [
            "modules.agent.presentation.controllers",
            "woobe_api.http.agent.routes",
            "modules.agent.presentation.schemas",
            "modules.agent.presentation.mappers",
        ]:
            sub = importlib.import_module(name)
            assert sub is not None

    def test_create_agent_presentation_layer_skeleton_rejects_forbidden_dependency(self):
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

