"""Cutover guard: all concrete worker code belongs to woobe-workers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "woobe-core" / "src"
WORKER_SRC = ROOT / "packages" / "woobe-workers" / "src" / "woobe_workers"


def test_legacy_and_core_worker_packages_are_removed() -> None:
    assert not (ROOT / "src" / "workers").exists()
    assert not (CORE_SRC / "shared" / "workers").exists()
    assert not list((CORE_SRC / "modules").glob("*/infra/workers"))


def test_worker_process_package_owns_concrete_consumers_and_runner() -> None:
    assert (WORKER_SRC / "consumers").is_dir()
    assert (WORKER_SRC / "runtime" / "runner.py").is_file()
