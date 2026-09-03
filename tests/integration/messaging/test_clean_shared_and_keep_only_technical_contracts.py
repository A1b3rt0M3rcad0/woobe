"""Integration tests for spec 096 — clean shared and keep only technical contracts.

Verifies that shared/ contains only technical contracts/bases after removing
domain layer, application layer, and concrete worker implementations.
"""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "shared"


def test_shared_domain_directory_removed():
    """shared/domain/ must not exist — domain code removed."""
    assert not (SHARED_DIR / "domain").is_dir(), (
        "shared/domain/ must be removed"
    )


def test_shared_application_directory_removed():
    """shared/application/ must not exist — application code removed."""
    assert not (SHARED_DIR / "application").is_dir(), (
        "shared/application/ must be removed"
    )


def test_core_shared_workers_package_is_removed():
    """Worker process primitives belong to woobe-workers, not Core shared."""
    assert not (SHARED_DIR / "workers").exists()


def test_worker_host_keeps_runtime_bases():
    worker_runtime = (
        ROOT / "packages" / "woobe-workers" / "src"
        / "woobe_workers" / "runtime"
    )
    bases = {
        "base_worker.py",
        "inbox_consumer_base.py",
        "inbox_processor_base.py",
        "outbox_dispatcher_base.py",
        "runner.py",
    }
    assert bases.issubset({path.name for path in worker_runtime.glob("*.py")})


def test_shared_infra_has_errors():
    """shared/infra/errors.py must exist — infra-level exceptions."""
    assert (SHARED_DIR / "infra" / "errors.py").is_file(), (
        "shared/infra/errors.py not found"
    )


def test_shared_messaging_has_outbox_writer():
    """shared/messaging/outbox_writer.py must exist — outbox contract."""
    assert (SHARED_DIR / "messaging" / "outbox_writer.py").is_file(), (
        "shared/messaging/outbox_writer.py not found"
    )


def test_shared_messaging_keeps_all_contracts():
    """All expected shared messaging contract modules must remain."""
    expected = {
        "event_envelope", "outbox_contracts", "inbox_contracts",
        "rabbitmq_topology", "retry_policy", "dead_letter_policy",
        "idempotency_contracts", "versioning_policy", "compatibility_policy",
        "outbox_writer",
    }
    msg_dir = SHARED_DIR / "messaging"
    existing = {p.stem for p in msg_dir.glob("*.py") if p.stem != "__init__"}
    missing = expected - existing
    assert not missing, (
        f"Missing messaging contracts: {missing}"
    )


def test_shared_infra_keeps_infrastructure():
    """shared/infra/ must retain technical infrastructure modules."""
    expected = {
        "crypto", "llm_usage", "rabbitmq", "errors",
    }
    infra_dir = SHARED_DIR / "infra"
    existing = {p.stem for p in infra_dir.glob("*.py") if p.stem != "__init__"}
    missing = expected - existing
    # config/, database/, repositories/ are subdirectories — test separately
    assert not missing, (
        f"Missing infra modules: {missing}"
    )


def test_shared_presentation_retained():
    """shared/presentation/ must be retained (HTTP infrastructure)."""
    assert (SHARED_DIR / "presentation").is_dir(), (
        "shared/presentation/ must exist"
    )
