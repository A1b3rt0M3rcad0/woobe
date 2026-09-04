from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "packages" / "woobe-core" / "src"
API_HTTP = ROOT / "packages" / "woobe-api" / "src" / "woobe_api" / "http"
RUNTIME_CONSUMERS = (
    CORE / "modules" / "agent",
    CORE / "modules" / "network",
    CORE / "modules" / "chat_surface",
)


def _python_files(root: Path):
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_runtime_consumers_do_not_construct_legacy_stream_readers() -> None:
    violations: list[str] = []
    for module_root in RUNTIME_CONSUMERS:
        for path in _python_files(module_root):
            source = path.read_text(encoding="utf-8")
            if "RuntimeStreamReader(" in source:
                violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, (
        "Runtime observation must pass through shared.runtime.RuntimeObserver; "
        "legacy RuntimeStreamReader construction found in:\n"
        + "\n".join(violations)
    )


def test_runtime_consumers_do_not_import_legacy_reattach_module() -> None:
    violations: list[str] = []
    for module_root in RUNTIME_CONSUMERS:
        for path in _python_files(module_root):
            source = path.read_text(encoding="utf-8")
            if "shared.runtime_reattach" in source:
                violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, (
        "Runtime consumers must import canonical shared.runtime primitives; "
        "legacy runtime_reattach imports found in:\n"
        + "\n".join(violations)
    )


def test_legacy_runtime_reattach_module_is_removed() -> None:
    assert not (CORE / "shared" / "runtime_reattach.py").exists()


def test_network_http_does_not_reimplement_acceptance_hot_wait() -> None:
    network_http = API_HTTP / "network"
    violations: list[str] = []
    for filename in ("runtime_routes.py", "reattach_routes.py"):
        path = network_http / filename
        source = path.read_text(encoding="utf-8")
        if "while hot is None" in source or "await asyncio.sleep(0.25)" in source:
            violations.append(path.relative_to(ROOT).as_posix())
    assert not violations, (
        "Acceptance -> hot-state waiting belongs to RuntimeObserver, not Network "
        "HTTP transport:\n" + "\n".join(violations)
    )


def test_public_runtime_dispatch_lives_in_api_composition_root() -> None:
    routes = (ROOT / "packages" / "woobe-api" / "src" / "public_runtime_routes.py").read_text(
        encoding="utf-8"
    )
    assert "from modules.agent" not in routes
    assert "from modules.network" not in routes
    assert "from runtime_composition import RUNTIME_HTTP" in routes


def test_canonical_runtime_observer_is_single_shared_boundary() -> None:
    observer = CORE / "shared" / "runtime" / "observer.py"
    source = observer.read_text(encoding="utf-8")
    assert source.count("class RuntimeObserver:") == 1
    assert "RunReference" in source
    assert "RuntimeStreamReader" in source
