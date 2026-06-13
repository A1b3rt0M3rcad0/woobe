from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
AGENT_DIR = SRC_DIR / "modules" / "agent"

EXPECTED_PACKAGES = [
    AGENT_DIR,
    AGENT_DIR / "domain",
    AGENT_DIR / "application",
    AGENT_DIR / "application" / "use_cases",
    AGENT_DIR / "application" / "dtos",
    AGENT_DIR / "application" / "handlers",
    AGENT_DIR / "application" / "composers",
    AGENT_DIR / "infra",
    AGENT_DIR / "infra" / "database",
    AGENT_DIR / "infra" / "llm",
    AGENT_DIR / "infra" / "messaging",
    AGENT_DIR / "infra" / "workers",
    AGENT_DIR / "presentation",
    AGENT_DIR / "presentation" / "controllers",
]


class TestCreateAgentModuleSkeleton:
    def test_create_agent_module_skeleton_success(self):
        for pkg_dir in EXPECTED_PACKAGES:
            assert pkg_dir.is_dir(), f"Directory missing: {pkg_dir}"
            init_file = pkg_dir / "__init__.py"
            assert init_file.is_file(), f"__init__.py missing: {init_file}"

        import importlib

        mod = importlib.import_module("modules.agent")
        assert mod is not None

    def test_create_agent_module_skeleton_rejects_forbidden_dependency(self):
        legacy_imports = [
            "from modules.ai",
            "from modules.knowledge",
            "from modules.runtime",
            "import modules.ai",
            "import modules.knowledge",
            "import modules.runtime",
        ]

        for pkg_dir in EXPECTED_PACKAGES:
            init_file = pkg_dir / "__init__.py"
            if not init_file.is_file():
                continue
            content = init_file.read_text(encoding="utf-8")
            for forbidden in legacy_imports:
                assert forbidden not in content, (
                    f"Forbidden import '{forbidden}' found in {init_file}"
                )
