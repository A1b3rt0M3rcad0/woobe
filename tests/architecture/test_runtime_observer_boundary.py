from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "packages" / "woobe-core" / "src"
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


def test_public_runtime_dispatch_lives_in_api_composition_root() -> None:
    routes = (ROOT / "packages" / "woobe-api" / "src" / "public_runtime_routes.py").read_text(
        encoding="utf-8"
    )
    assert "from modules.agent" not in routes
    assert "from modules.network" not in routes
    assert "from composition.runtime import RUNTIME_HTTP" in routes


def test_canonical_runtime_observer_is_single_shared_boundary() -> None:
    observer = CORE / "shared" / "runtime" / "observer.py"
    source = observer.read_text(encoding="utf-8")
    assert source.count("class RuntimeObserver:") == 1
    assert "RunReference" in source
    assert "RuntimeStreamReader" in source
