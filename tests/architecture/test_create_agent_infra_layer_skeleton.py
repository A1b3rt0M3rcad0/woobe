from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
INFRA_DIR = SRC_DIR / "modules" / "agent" / "infra"

EXPECTED_FILES = [
    INFRA_DIR / "__init__.py",
    INFRA_DIR / "database" / "__init__.py",
    INFRA_DIR / "database" / "models.py",
    INFRA_DIR / "database" / "repositories.py",
    INFRA_DIR / "database" / "mappers.py",
    INFRA_DIR / "database" / "unit_of_work.py",
    INFRA_DIR / "llm" / "__init__.py",
    INFRA_DIR / "llm" / "langchain_factory.py",
    INFRA_DIR / "llm" / "providers.py",
    INFRA_DIR / "messaging" / "__init__.py",
    INFRA_DIR / "messaging" / "publishers.py",
    INFRA_DIR / "messaging" / "consumers.py",
    INFRA_DIR / "messaging" / "event_mappers.py",
    INFRA_DIR / "workers" / "__init__.py",
    INFRA_DIR / "workers" / "outbox_dispatcher.py",
    INFRA_DIR / "workers" / "inbox_consumer.py",
    INFRA_DIR / "workers" / "inbox_processor.py",
    INFRA_DIR / "workers" / "registry.py",
]


class TestCreateAgentInfraLayerSkeleton:
    def test_create_agent_infra_layer_skeleton_success(self):
        assert INFRA_DIR.is_dir(), f"Infra directory missing: {INFRA_DIR}"

        for filepath in EXPECTED_FILES:
            assert filepath.is_file(), f"Infra skeleton file missing: {filepath}"

        import importlib

        mod = importlib.import_module("modules.agent.infra")
        assert mod is not None

        for name in [
            "modules.agent.infra.database",
            "modules.agent.infra.database.models",
            "modules.agent.infra.database.repositories",
            "modules.agent.infra.database.mappers",
            "modules.agent.infra.database.unit_of_work",
            "modules.agent.infra.llm",
            "modules.agent.infra.llm.langchain_factory",
            "modules.agent.infra.llm.providers",
            "modules.agent.infra.messaging",
            "modules.agent.infra.messaging.publishers",
            "modules.agent.infra.messaging.consumers",
            "modules.agent.infra.messaging.event_mappers",
            "woobe_workers.consumers.agent",
            "woobe_workers.consumers.agent.outbox_dispatcher",
            "woobe_workers.consumers.agent.inbox_consumer",
            "woobe_workers.consumers.agent.inbox_processor",
            "modules.agent.composition.worker_runtime.registry",
        ]:
            sub = importlib.import_module(name)
            assert sub is not None

    def test_create_agent_infra_layer_skeleton_rejects_forbidden_dependency(self):
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
