from __future__ import annotations

import importlib
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerRegistryProtocol

logger = logging.getLogger(__name__)

CORE_MODULE_WORKER_REGISTRIES: tuple[str, ...] = (
    "agent",
    "core",
    "identity",
    "metering",
    "network",
    "observability",
)


class ModuleWorkerEntry:
    def __init__(
        self,
        module_name: str,
        registry_class: type[WorkerRegistryProtocol],
        register_func: Any,
    ) -> None:
        self.module_name = module_name
        self.registry_class = registry_class
        self.register_func = register_func


def discover_module_entries() -> list[ModuleWorkerEntry]:
    module_paths = [
        (
            module_name,
            "modules.agent.entrypoint"
            if module_name == "agent"
            else f"modules.{module_name}.infra.workers.registry",
        )
        for module_name in CORE_MODULE_WORKER_REGISTRIES
    ]

    entries: list[ModuleWorkerEntry] = []
    for module_name, module_path in module_paths:
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            logger.warning("Could not import registry for module %s: %s", module_name, exc)
            continue

        cls_name = f"{module_name.capitalize()}WorkerRegistry"
        registry_cls = getattr(mod, cls_name, None)
        func_name = f"register_{module_name}_workers"
        register_func = getattr(mod, func_name, None)

        if registry_cls is None:
            logger.warning("Module %s has no %s", module_name, cls_name)
            continue

        if register_func is None:
            logger.warning("Module %s has no %s", module_name, func_name)
            continue

        entries.append(
            ModuleWorkerEntry(
                module_name=module_name,
                registry_class=registry_cls,
                register_func=register_func,
            )
        )
    return entries


def build_registries(
    entries: list[ModuleWorkerEntry],
    engine: AsyncEngine,
    settings: Any,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> list[WorkerRegistryProtocol]:
    registries: list[WorkerRegistryProtocol] = []
    for entry in entries:
        registry = entry.registry_class()
        entry.register_func(
            registry,
            settings=settings,
            engine=engine,
            rabbitmq_manager=rabbitmq_manager,
        )
        registries.append(registry)
    return registries
