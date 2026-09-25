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


def test_release_candidate_builds_exactly_four_process_images() -> None:
    candidate = (ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )
    images = set(re.findall(r"\n\s+image: (woobe-[a-z-]+)", candidate))
    assert images == CONTAINER_RELEASE_UNITS
    assert "target: api" in candidate
    assert "target: workers" in candidate
    assert "dockerfile: packages/woobe-frontend/Dockerfile" in candidate
    assert "dockerfile: packages/woobe-embed/Dockerfile" in candidate
    assert "platforms: linux/amd64,linux/arm64" in candidate
    assert "provenance: mode=max" in candidate
    assert "sbom: true" in candidate
    assert "sha-$revision" in candidate


def test_release_promotes_candidate_without_rebuilding() -> None:
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "docker/build-push-action" not in release
    assert "docker build " not in release
    assert "docker buildx imagetools create" in release
    assert 'candidate_tag="sha-${{ steps.meta.outputs.revision }}"' in release
    assert 'test "$target_digest" = "$source_digest"' in release
    assert "post-publish-smoke:" in release
    assert "smoke_prebuilt_core_images.sh" in release
    assert "/woobe-core:" not in release


def test_release_identity_uses_canonical_version_not_commit_subject() -> None:
    candidate = (ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    prepare = (ROOT / ".github/workflows/prepare-release.yml").read_text(
        encoding="utf-8"
    )

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert "Detect platform release transition" in candidate
    assert "paths:\n      - VERSION" in candidate
    assert "python scripts/ci/check_package_versions.py" in candidate
    assert 'version="$(tr -d \'[:space:]\' < VERSION)"' in candidate
    assert "git log -1 --format=%s" not in candidate
    assert "startsWith(github.event.head_commit.message" not in candidate

    assert 'test "$version" = "${{ inputs.version }}"' in release
    assert 'git rev-parse "v${{ inputs.version }}^{commit}"' in release
    assert "git log -1 --format=%s" not in release

    assert "scripts/release/set_platform_version.py" in prepare
    assert "gh pr create" in prepare
    assert "WOOBE_RELEASE_TOKEN" in prepare
    assert "<<EOF" not in prepare
    assert "Unable to create the release pull request" in prepare
    assert "Dispatch release-branch validation" in prepare
    assert "workflow run cla.yml" in prepare


def test_platform_version_sync_script_covers_release_mirrors() -> None:
    sync = (ROOT / "scripts/release/set_platform_version.py").read_text(
        encoding="utf-8"
    )
    check = (ROOT / "scripts/ci/check_package_versions.py").read_text(
        encoding="utf-8"
    )

    for path in (
        "pyproject.toml",
        "packages/woobe-core/pyproject.toml",
        "packages/woobe-api/pyproject.toml",
        "packages/woobe-workers/pyproject.toml",
        "packages/woobe-runtime-client/package.json",
        "packages/woobe-ui/package.json",
        "packages/woobe-frontend/package.json",
        "packages/woobe-embed/package.json",
        "packages/woobe-frontend/package-lock.json",
        "packages/woobe-embed/package-lock.json",
        "uv.lock",
        "packages/woobe-api/src/main.py",
        "packages/woobe-core/src/modules/agent/application/mcp_discovery.py",
        "packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py",
    ):
        assert path in sync

    assert '_canonical_version()' in check
    assert 'ROOT / "VERSION"' in check
    assert '"uv.lock": _uv_project_version()' in check


def test_container_ci_reproduces_release_candidate_multiarch_contract() -> None:
    candidate = (ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )
    containers = (ROOT / ".github/workflows/containers.yml").read_text(
        encoding="utf-8"
    )

    assert "release-multiarch-build:" in containers
    assert "runs-on: ubuntu-latest" in containers
    assert containers.count("platforms: linux/amd64,linux/arm64") == 4
    assert containers.count("push: false") == 4
    assert "docker/setup-qemu-action@v3" in containers
    assert "docker/setup-buildx-action@v3" in containers

    for token in (
        "target: api",
        "target: workers",
        "packages/woobe-frontend/Dockerfile",
        "packages/woobe-embed/Dockerfile",
    ):
        assert token in candidate
        assert token in containers


def test_release_candidate_sha_tags_are_reused_not_overwritten() -> None:
    candidate = (ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )

    assert "Check immutable candidate existence" in candidate
    assert "steps.candidate.outputs.exists != 'true'" in candidate
    assert "Verify immutable candidate identity" in candidate
    assert "org.opencontainers.image.revision" in candidate
    assert "org.opencontainers.image.version" in candidate


def test_acceptance_validates_previous_release_upgrade() -> None:
    acceptance = (ROOT / ".github/workflows/acceptance.yml").read_text(
        encoding="utf-8"
    )
    upgrade = (ROOT / "scripts/ci/validate_previous_release_upgrade.sh").read_text(
        encoding="utf-8"
    )

    assert "previous-release-upgrade:" in acceptance
    assert "validate_previous_release_upgrade.sh" in acceptance
    assert "git tag --merged" in upgrade
    assert "docker manifest inspect" in upgrade
    assert "published API image" in upgrade
    assert "head -n 1" not in upgrade
    assert "ghcr.io/" in upgrade
    assert "alembic" in upgrade
    assert "release-upgrade-probe" in upgrade


def test_prebuilt_image_smoke_contract_covers_all_container_units() -> None:
    override = (ROOT / "docker/ci/compose.release-images.yml").read_text(
        encoding="utf-8"
    )
    smoke = (ROOT / "scripts/ci/smoke_prebuilt_core_images.sh").read_text(
        encoding="utf-8"
    )

    for variable in (
        "WOOBE_API_IMAGE",
        "WOOBE_WORKERS_IMAGE",
        "WOOBE_FRONTEND_IMAGE",
        "WOOBE_EMBED_IMAGE",
    ):
        assert variable in override
        assert variable in smoke
    assert "--no-build" in smoke
    assert "smoke_production.sh" in smoke
    assert "WOOBE_WORKER_HEALTH_FILE" in smoke


def test_compose_selects_api_and_workers_targets_explicitly() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "target: api" in compose
    assert "target: workers" in compose
