from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _py_modules(package: str) -> set[str]:
    pyproject = ROOT / "packages" / package / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return set(data["tool"]["setuptools"]["py-modules"])


def test_api_runtime_composition_is_installed_with_process_package() -> None:
    source = ROOT / "packages" / "woobe-api" / "src"
    assert "runtime_composition" in _py_modules("woobe-api")
    assert (source / "runtime_composition.py").is_file()
    assert not (source / "composition").exists()
    routes = (source / "public_runtime_routes.py").read_text(encoding="utf-8")
    assert "from runtime_composition import RUNTIME_HTTP" in routes


def test_worker_network_agent_composition_is_installed_with_process_package() -> None:
    source = ROOT / "packages" / "woobe-workers" / "src"
    assert "network_agent_runtime_composition" in _py_modules("woobe-workers")
    assert (source / "network_agent_runtime_composition.py").is_file()
    assert not (source / "composition").exists()
    worker_main = (source / "worker_main.py").read_text(encoding="utf-8")
    assert "from network_agent_runtime_composition import ProjectRAIAgentInvoker" in worker_main
