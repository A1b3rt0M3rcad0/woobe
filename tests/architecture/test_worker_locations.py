"""Architecture guards for the worker-host ownership boundary."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "woobe-core" / "src"
WORKER_SRC = ROOT / "packages" / "woobe-workers" / "src"
WORKER_PACKAGE = WORKER_SRC / "woobe_workers"
MODULES = ("agent", "core", "identity", "metering", "network", "observability")


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
        elif isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
    return tuple(values)


def test_core_contains_no_worker_implementation_or_process_runtime() -> None:
    forbidden = [
        CORE_SRC / "shared" / "workers",
        CORE_SRC / "shared" / "observability" / "worker_health.py",
        CORE_SRC / "modules" / "agent" / "composition" / "workers.py",
    ]
    forbidden.extend(
        CORE_SRC / "modules" / module / "infra" / "workers"
        for module in MODULES
    )
    assert not [path for path in forbidden if path.exists()]


def test_core_never_depends_on_worker_host() -> None:
    violations = [
        path.relative_to(ROOT).as_posix()
        for path in CORE_SRC.rglob("*.py")
        if any(name == "woobe_workers" or name.startswith("woobe_workers.") for name in _imports(path))
    ]
    assert not violations, "woobe-core imports woobe-workers:\n" + "\n".join(violations)


def test_worker_host_owns_runtime_registries_and_concrete_consumers() -> None:
    assert (WORKER_SRC / "worker_main.py").is_file()
    assert (WORKER_PACKAGE / "contracts.py").is_file()
    assert (WORKER_PACKAGE / "runtime" / "runner.py").is_file()
    assert (WORKER_PACKAGE / "runtime" / "health.py").is_file()
    assert (WORKER_PACKAGE / "composition" / "registries.py").is_file()
    for module in MODULES:
        consumer = WORKER_PACKAGE / "consumers" / module
        assert consumer.is_dir(), f"missing consumer package: {module}"
        assert (consumer / "registry.py").is_file(), f"missing registry: {module}"


def test_worker_host_enters_modules_only_through_public_boundaries() -> None:
    violations: list[str] = []
    for path in WORKER_SRC.rglob("*.py"):
        for imported in _imports(path):
            if imported == "modules" or imported.startswith("modules."):
                parts = imported.split(".")
                public = (
                    len(parts) == 3
                    and parts[0] == "modules"
                    and parts[2] in {"entrypoint", "background_boundary"}
                )
                if not public:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports {imported}"
                    )
    assert not violations, "worker consumers bypass public boundaries:\n" + "\n".join(violations)


def test_background_boundaries_are_one_way_and_transport_neutral() -> None:
    violations: list[str] = []
    for module in MODULES:
        boundary = CORE_SRC / "modules" / module / "background_boundary.py"
        assert boundary.is_file(), f"missing public background boundary: {module}"
        for imported in _imports(boundary):
            if imported == "woobe_workers" or imported.startswith("woobe_workers."):
                violations.append(f"{boundary.relative_to(ROOT)} imports {imported}")
            if ".presentation" in imported:
                violations.append(f"{boundary.relative_to(ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_worker_package_does_not_depend_on_http_presentation() -> None:
    violations = [
        f"{path.relative_to(ROOT).as_posix()} imports {imported}"
        for path in WORKER_SRC.rglob("*.py")
        for imported in _imports(path)
        if imported.startswith("modules.") and ".presentation" in imported
    ]
    assert not violations, "\n".join(violations)


def test_process_only_settings_are_not_owned_by_core_settings() -> None:
    core_config = (CORE_SRC / "shared" / "infra" / "config" / "config.py").read_text(encoding="utf-8")
    worker_settings = (WORKER_PACKAGE / "settings.py").read_text(encoding="utf-8")
    process_fields = (
        "network_worker_prefetch",
        "network_worker_slots",
        "worker_interval",
        "worker_health_file",
        "worker_heartbeat_interval_seconds",
        "worker_health_max_age_seconds",
    )
    assert all(field not in core_config for field in process_fields)
    assert all(field in worker_settings for field in process_fields)
