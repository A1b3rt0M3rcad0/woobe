from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
DOMAIN_DIR = SRC_DIR / "modules" / "agent" / "domain"

EXPECTED_FILES = [
    DOMAIN_DIR / "__init__.py",
    DOMAIN_DIR / "entities.py",
    DOMAIN_DIR / "value_objects.py",
    DOMAIN_DIR / "events.py",
    DOMAIN_DIR / "enums.py",
    DOMAIN_DIR / "errors.py",
    DOMAIN_DIR / "repositories.py",
    DOMAIN_DIR / "services.py",
]


class TestCreateAgentDomainLayerSkeleton:
    def test_create_agent_domain_layer_skeleton_success(self):
        assert DOMAIN_DIR.is_dir(), f"Domain directory missing: {DOMAIN_DIR}"

        for filepath in EXPECTED_FILES:
            assert filepath.is_file(), f"Domain skeleton file missing: {filepath}"

        import importlib

        mod = importlib.import_module("modules.agent.domain")
        assert mod is not None

        for name in [
            "entities",
            "value_objects",
            "events",
            "enums",
            "errors",
            "repositories",
            "services",
        ]:
            sub = importlib.import_module(f"modules.agent.domain.{name}")
            assert sub is not None

    def test_create_agent_domain_layer_skeleton_rejects_forbidden_dependency(self):
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
