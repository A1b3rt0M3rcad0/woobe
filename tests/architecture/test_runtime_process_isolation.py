from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_bootstrap_does_not_start_background_workers() -> None:
    import src.main as main_module

    source = inspect.getsource(main_module)
    assert "WorkerRunner" not in source
    assert "RabbitMQManager" not in source
    assert "discover_module_entries" not in source
    assert "build_registries" not in source


def test_worker_bootstrap_owns_messaging_and_worker_lifecycle() -> None:
    import src.worker_main as worker_module

    source = inspect.getsource(worker_module)
    assert "RabbitMQManager" in source
    assert "discover_module_entries" in source
    assert "build_registries" in source
    assert "WorkerRunner.from_registries" in source
    assert "await runner.start()" in source
    assert "await runner.stop()" in source
    assert "signal.SIGTERM" in source


def test_default_community_compose_keeps_processes_and_optional_infra_separate() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8-sig")

    for service in ("db", "rabbitmq", "migrate", "api", "workers", "web", "chat-embed"):
        assert f"\n  {service}:\n" in compose
    for optional_service in ("pgbouncer", "redis", "minio", "rabbitmq-observer"):
        assert f"\n  {optional_service}:\n" not in compose

    assert 'command: ["python", "-m", "src.worker_main"]' in compose
    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert "condition: service_completed_successfully" in compose


def test_repository_has_one_default_community_compose_contract() -> None:
    assert (ROOT / "compose.yaml").is_file()
    assert (ROOT / "deploy" / "dev" / "compose.yml").is_file()

    for legacy_name in (
        "compose.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
    ):
        assert not (ROOT / legacy_name).exists()


def test_docker_entrypoint_never_runs_migrations_implicitly() -> None:
    entrypoint = (ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8-sig")
    assert "alembic" not in entrypoint.lower()
    assert 'exec "$@"' in entrypoint
