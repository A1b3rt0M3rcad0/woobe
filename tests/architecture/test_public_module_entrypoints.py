import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"

ALL_MODULES = {"agent", "identity", "core", "billing", "metering", "observability", "tools"}

MODULES_WITH_WORKER_REGISTRY = {"agent", "identity", "billing", "metering", "observability", "tools"}


class TestPublicModuleEntrypoints:
    def test_module_init_exposes_routes(self):
        for module_name in sorted(ALL_MODULES):
            mod = importlib.import_module(f"modules.{module_name}")
            assert hasattr(mod, "routes"), (
                f"{module_name}.__init__ must expose 'routes'"
            )

    def test_module_init_exposes_worker_registry_when_present(self):
        for module_name in sorted(MODULES_WITH_WORKER_REGISTRY):
            mod = importlib.import_module(f"modules.{module_name}")
            assert hasattr(mod, "registry"), (
                f"{module_name}.__init__ must expose 'registry'"
            )

    def test_module_has_all_list(self):
        for module_name in sorted(ALL_MODULES):
            mod = importlib.import_module(f"modules.{module_name}")
            assert hasattr(mod, "__all__"), (
                f"{module_name}.__init__ must define __all__"
            )
            assert len(mod.__all__) >= 1, (
                f"{module_name}.__init__.__all__ must not be empty"
            )

    def test_bootstrap_can_import_routes(self):
        for module_name in sorted(ALL_MODULES):
            routes_mod = importlib.import_module(f"modules.{module_name}.presentation.routes")
            assert routes_mod is not None, (
                f"modules.{module_name}.presentation.routes must be importable"
            )

    def test_bootstrap_can_import_worker_registry(self):
        for module_name in sorted(MODULES_WITH_WORKER_REGISTRY):
            registry_mod = importlib.import_module(
                f"modules.{module_name}.infra.workers.registry"
            )
            assert registry_mod is not None, (
                f"modules.{module_name}.infra.workers.registry must be importable"
            )
