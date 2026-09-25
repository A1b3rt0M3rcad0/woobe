"""Release-unit boundaries for the five primary Woobe product packages."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PRIMARY_RELEASE_UNITS = {
    "woobe-core",
    "woobe-api",
    "woobe-workers",
    "woobe-frontend",
    "woobe-embed",
}
CONTAINER_RELEASE_UNITS = {
    "woobe-api",
    "woobe-workers",
    "woobe-frontend",
    "woobe-embed",
}


def _project_dependencies(package: str) -> set[str]:
    data = tomllib.loads(
        (ROOT / "packages" / package / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = data["project"].get("dependencies", [])
    return {
        re.split(r"[<>=!~\[]", dependency, maxsplit=1)[0].strip()
        for dependency in dependencies
    }


def _stage(dockerfile: str, name: str, next_name: str | None = None) -> str:
    start = dockerfile.index(f"FROM runtime-base AS {name}")
    if next_name is None:
        return dockerfile[start:]
    end = dockerfile.index(f"FROM runtime-base AS {next_name}", start)
    return dockerfile[start:end]


def test_primary_release_units_are_explicit() -> None:
    packages = (ROOT / "packages" / "README.md").read_text(encoding="utf-8")
    for package in PRIMARY_RELEASE_UNITS:
        assert f"`{package}`" in packages


def test_backend_process_packages_depend_in_one_direction_only() -> None:
    core_dependencies = _project_dependencies("woobe-core")
    api_dependencies = _project_dependencies("woobe-api")
    worker_dependencies = _project_dependencies("woobe-workers")

    assert "woobe-api" not in core_dependencies
    assert "woobe-workers" not in core_dependencies
    assert "woobe-core" in api_dependencies
    assert "woobe-workers" not in api_dependencies
    assert "woobe-core" in worker_dependencies
    assert "woobe-api" not in worker_dependencies


def test_api_and_workers_images_have_distinct_source_boundaries() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    workers = _stage(dockerfile, "workers", "api")
    api = _stage(dockerfile, "api")

    assert "packages/woobe-workers/src/" in workers
    assert "packages/woobe-api/src/" not in workers

    assert "packages/woobe-api/src/" in api
    assert "packages/woobe-workers/src/" not in api


def test_browser_release_units_are_built_independently() -> None:
    web = (ROOT / "packages/woobe-frontend/Dockerfile").read_text(encoding="utf-8")
    embed = (ROOT / "packages/woobe-embed/Dockerfile").read_text(encoding="utf-8")

    assert "packages/woobe-embed" not in web
    assert "packages/woobe-frontend" not in embed
    assert "packages/woobe-runtime-client" in web
    assert "packages/woobe-runtime-client" in embed


def test_release_workflow_publishes_exactly_four_process_images() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    published = set(
        re.findall(r"/(woobe-[a-z-]+):\$\{\{ inputs\.version \}\}", workflow)
    )
    assert published == CONTAINER_RELEASE_UNITS
    assert "target: api" in workflow
    assert "target: workers" in workflow
    assert "/woobe-core:" not in workflow


def test_compose_selects_api_and_workers_targets_explicitly() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "target: api" in compose
    assert "target: workers" in compose
