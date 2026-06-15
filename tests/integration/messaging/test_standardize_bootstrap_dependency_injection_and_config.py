"""Integration tests for spec 097 — standardize bootstrap, DI, and config.

Validates that each module has a proper bootstrap pattern: routes,
UoW factories, registries, and settings without service locator.
"""
from __future__ import annotations

import importlib

MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def test_each_module_has_routes():
    """Every canonical module has a presentation.routes module."""
    for mod_name in MODULES:
        mod = importlib.import_module(f"modules.{mod_name}.presentation.routes")
        assert hasattr(mod, "router")


def test_each_module_has_unit_of_work():
    """Every canonical module has a UoW with outbox property."""
    for mod_name in MODULES:
        mod = importlib.import_module(
            f"modules.{mod_name}.infra.database.unit_of_work"
        )
        uow_name = f"{mod_name.capitalize()}UnitOfWork"
        uow_cls = getattr(mod, uow_name, None)
        assert uow_cls is not None, (
            f"{mod_name} missing {uow_name}"
        )
        assert hasattr(uow_cls, "outbox"), (
            f"{uow_name} missing outbox property"
        )


def test_each_module_has_worker_registry():
    """Every canonical module has a registry with register_*_workers function."""
    for mod_name in MODULES:
        mod = importlib.import_module(
            f"modules.{mod_name}.infra.workers.registry"
        )
        registry_fn = getattr(mod, f"register_{mod_name}_workers", None)
        assert registry_fn is not None, (
            f"{mod_name} missing register_{mod_name}_workers"
        )
        assert callable(registry_fn)


def test_each_module_has_settings_import():
    """Settings must be importable from shared.infra.config."""
    from shared.infra.config import Settings
    required = {"database_url", "rabbitmq_url", "rabbitmq_exchange",
                "cors_origins", "secret_key", "encryption_key"}
    existing = set(Settings.model_fields.keys())
    missing = required - existing
    assert not missing, f"Settings missing: {missing}"


def test_main_imports_all_module_routers():
    """src.main must import and register all module routers."""
    import inspect
    import src.main as main_mod
    source = inspect.getsource(main_mod)
    for mod_name in MODULES:
        assert f"modules.{mod_name}.presentation.routes" in source, (
            f"main.py missing import for {mod_name}"
        )
