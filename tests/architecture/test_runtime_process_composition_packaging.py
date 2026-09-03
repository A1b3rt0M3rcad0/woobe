from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_worker_process_package_installs_composition_and_consumers() -> None:
    package_root = ROOT / "packages" / "woobe-workers"
    source = package_root / "src"
    data = tomllib.loads((package_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["setuptools"]["py-modules"] == ["worker_main"]
    assert data["tool"]["setuptools"]["packages"]["find"]["include"] == ["woobe_workers*"]
    assert (source / "worker_main.py").is_file()
    assert (source / "woobe_workers" / "composition" / "registries.py").is_file()
    assert (source / "woobe_workers" / "consumers" / "agent" / "registry.py").is_file()
