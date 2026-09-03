from __future__ import annotations

import importlib
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import ModuleWorkerEntry, WorkerRegistryProtocol

logger = logging.getLogger(__name__)

CORE_MODULE_WORKER_REGISTRIES: tuple[str, ...] = (
    "agent",
    "core",
    "identity",
    "metering",
    "network",
    "observability",
)


def discover_module_entries() -> list[ModuleWorkerEntry]:
    entries: list[ModuleWorkerEntry] = []
    for module_name in CORE_MODULE_WORKER_REGISTRIES:
        module_path = (
            "modules.agent.entrypoint"
            if module_name == "agent"
            else f"modules.{module_name}.infra.workers.registry"
        )
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            logger.warning(
                "Could not import registry for module %s: %s",
                module_name,
                exc,
            )
            continue

        registry_name = f"{module_name.capitalize()}WorkerRegistry"
        registry_class = getattr(module, registry_name, None)
        register_name = f"register_{module_name}_workers"
        register_func = getattr(module, register_name, None)
        if registry_class is None:
            logger.warning("Module %s has no %s", module_name, registry_name)
            continue
        if register_func is None:
            logger.warning("Module %s has no %s", module_name, register_name)
            continue

        entries.append(
            ModuleWorkerEntry(
                module_name=module_name,
                registry_class=registry_class,
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
