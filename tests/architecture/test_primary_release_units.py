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
    assert "ubuntu-24.04" in candidate


def test_release_promotes_candidate_without_rebuilding() -> None:
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "docker/build-push-action" not in release
    assert "docker build " not in release
    assert "docker buildx imagetools create" in release
    assert 'candidate_tag="sha-$REVISION"' in release
    assert "Preflight release version targets" in release
    assert release.index("Preflight release version targets") < release.index(
        "Promote exact validated digests to release version"
    )
    assert "Promote exact validated digests to release version" in release
    assert 'test "$target_digest" = "$digest"' in release
    assert "post-publish-smoke:" in release
    assert "tag:" in release
    assert "needs: [publish, post-publish-smoke]" in release
    assert "needs: [publish, post-publish-smoke, tag]" in release
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
    assert "Detect platform release transition" not in candidate
    assert "push:\n    branches: [master]" not in candidate
    assert "workflow_call:" in candidate
    assert "workflow_dispatch:" in candidate
    assert "python scripts/ci/check_package_versions.py" in candidate
    assert 'version="$(tr -d \'[:space:]\' < VERSION)"' in candidate
    assert "git log -1 --format=%s" not in candidate
    assert "startsWith(github.event.head_commit.message" not in candidate

    assert "push:\n    tags:" not in release
    assert "workflow_call:" in release
    assert "workflow_dispatch:" not in release
    assert "validation_id:" in release
    assert "api_digest:" in release
    assert 'test "$revision" = "$EXPECTED_REVISION"' in release
    assert "Immutable release tag $tag does not exist." not in release
    assert 'git rev-parse "$tag^{commit}"' in release
    assert "git log -1 --format=%s" not in release

    assert "name: Release Woobe" in prepare
    assert "scripts/release/set_platform_version.py" in prepare
    assert "gh pr create" in prepare
    assert "--draft" not in prepare
    assert "WOOBE_RELEASE_TOKEN" in prepare
    assert "textwrap.dedent" in prepare
    assert "<<EOF" not in prepare
    assert "git push origin --delete" in release
    assert "Unable to create the release pull request" in prepare
    assert "orchestrate_release_pr.py" in prepare
    assert "uses: ./.github/workflows/release-candidate.yml" in prepare
    assert "uses: ./.github/workflows/release.yml" in prepare
    assert "dispatch_and_wait.py" not in prepare
    assert "resume_finalization" in prepare
    assert "expected_version: ${{ needs.prepare.outputs.version }}" in prepare
    assert "target {version} must be newer than latest published release" in prepare


def test_validated_release_candidate_is_bound_to_one_orchestrated_publication() -> None:
    candidate = (ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    prepare = (ROOT / ".github/workflows/prepare-release.yml").read_text(
        encoding="utf-8"
    )

    assert "finalize-release:" not in candidate
    assert "push:\n    branches: [master]" not in candidate
    assert "workflow_call:" in candidate
    assert "validation_id:" in candidate
    assert "api_digest:" in candidate
    assert "actions/upload-artifact" not in candidate
    assert "group: release-candidate-${{ inputs.ref }}" in candidate
    assert "cancel-in-progress: false" in candidate

    assert "push:\n    tags:" not in release
    assert "workflow_call:" in release
    assert "validation_id:" in release
    assert "api_digest:" in release
    assert "Promote exact validated digests to release version" in release
    assert "Registry state is unknown" in release
    assert "Immutable release image already exists with a different digest" in release
    assert "release-manifest.json" in release
    assert "gh release create" in release
    assert "--generate-notes" in release
    assert "Remove completed release branch" in release
    assert "group: publish-woobe-${{ inputs.version }}" in release
    assert "cancel-in-progress: false" in release

    assert "uses: ./.github/workflows/release-candidate.yml" in prepare
    assert "uses: ./.github/workflows/release.yml" in prepare
    assert "Create or verify immutable release tag" not in prepare
    assert "Create or verify immutable release tag" in release
    assert "Preflight release version targets" in release
    assert "Verify completed release recovery" in prepare
    assert "Complete pending release branch cleanup" in prepare
    assert "${{ github.run_id }}-${{ github.run_attempt }}" in prepare
    assert "Release Woobe v${{ inputs.version }}" in prepare
    assert 'GITHUB_REF" != "refs/heads/master' in prepare


def test_release_workflows_pin_hosted_runner_and_action_commits() -> None:
    for relative in (
        ".github/workflows/prepare-release.yml",
        ".github/workflows/release-candidate.yml",
        ".github/workflows/release.yml",
    ):
        workflow = (ROOT / relative).read_text(encoding="utf-8")
        assert "ubuntu-latest" not in workflow
        assert "ubuntu-24.04" in workflow
        for action in re.findall(r"uses:\s+([^\s#]+)", workflow):
            if action.startswith("./"):
                continue
            assert re.search(r"@[0-9a-f]{40}$", action), (relative, action)


def test_release_orchestrator_requires_exact_green_head_before_merge() -> None:
    orchestrator = (ROOT / "scripts/release/orchestrate_release_pr.py").read_text(
        encoding="utf-8"
    )
    cla = (ROOT / ".github/workflows/cla.yml").read_text(encoding="utf-8")

    for workflow in (
        "Backend test suite",
        "Frontend test and build",
        "Package Build",
        "Acceptance",
        "Quality Gate",
        "Container quality",
        "Security audit",
        "CLA acceptance",
    ):
        assert workflow in orchestrator

    assert "ALLOWED_RELEASE_PATHS" in orchestrator
    assert "check_package_versions.py" in orchestrator
    assert "merge-base" in orchestrator
    assert "--match-head-commit" in orchestrator
    assert "Nothing was merged, tagged, or published." in orchestrator
    assert "Release gate passed" in orchestrator
    compile(orchestrator, "scripts/release/orchestrate_release_pr.py", "exec")

    assert 'AUTHOR_LOGIN: ${{ steps.pr.outputs.author_login }}' in cla
    assert 'HEAD_REPO: ${{ steps.pr.outputs.head_repo }}' in cla
    assert 'HEAD_REF: ${{ steps.pr.outputs.head_ref }}' in cla
    assert '"$AUTHOR_LOGIN" == "github-actions[bot]"' in cla
    assert '"$HEAD_REF" == release/*' in cla


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

    assert "Phase · release-multiarch-build" in containers
    assert "runs-on: [self-hosted, Linux, X64]" in containers
    assert "runs-on: ubuntu-24.04" not in containers
    assert containers.count("runs-on:") == 1
    assert containers.count("platforms: linux/amd64,linux/arm64") == 4
    assert containers.count("push: false") == 4
    assert "docker/setup-qemu-action@99012661954931238ded8c8b007157a8430204e1" in containers
    assert "docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069" in containers

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

    assert "Probe immutable candidate" in candidate
    assert "steps.candidate.outputs.state == 'missing'" in candidate
    assert "Candidate lookup failed" in candidate
    assert "Unable to determine whether immutable candidate exists" in candidate
    assert "manifest unknown|no such manifest|not found" in candidate
    assert "Verify immutable candidate identity" in candidate
    assert "org.opencontainers.image.revision" in candidate
    assert "org.opencontainers.image.version" in candidate
    assert "actions/upload-artifact" not in candidate
    assert "digest_with_retry" in candidate



def test_release_ci_pins_required_actions_and_runs_release_contract_tests() -> None:
    required = (
        "tests.yml",
        "frontend.yml",
        "package-build.yml",
        "acceptance.yml",
        "quality-gate.yml",
        "containers.yml",
        "security.yml",
        "cla.yml",
    )
    for filename in required:
        workflow = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
        assert "runs-on: [self-hosted, Linux, X64]" in workflow
        assert "runs-on: ubuntu-24.04" not in workflow
        assert "continue-on-error: true" not in workflow
        assert "outcome: ${{ job.status }}" not in workflow
        assert workflow.count("runs-on:") == 1
        for action in re.findall(r"uses:\s+([^\s#]+)", workflow):
            if action.startswith("./"):
                continue
            assert re.search(r"@[0-9a-f]{40}$", action), (filename, action)

    quality = (ROOT / ".github/workflows/quality-gate.yml").read_text(encoding="utf-8")
    assert "tests/architecture/test_primary_release_units.py" in quality
    assert "tests/unit/test_release_orchestrator.py" in quality
    assert "tests/unit/test_release_workflow_graph.py" in quality
    assert "tests/unit/test_release_registry_state_machine.py" in quality
    assert "github.com/rhysd/actionlint/cmd/actionlint@v1.7.7" in quality
    assert '".github/workflows/release.yml"' in quality
    assert '"scripts/release/**"' in quality


def test_acceptance_validates_previous_release_upgrade() -> None:
    acceptance = (ROOT / ".github/workflows/acceptance.yml").read_text(
        encoding="utf-8"
    )
    upgrade = (ROOT / "scripts/ci/validate_previous_release_upgrade.sh").read_text(
        encoding="utf-8"
    )

    assert "Phase · previous-release-upgrade" in acceptance
    assert acceptance.count("runs-on:") == 1
    assert 'docker exec --user 999:999 "$WOOBE_ACCEPTANCE_RABBITMQ_CONTAINER"' in acceptance
    assert "validate_previous_release_upgrade.sh" in acceptance
    assert "git tag --merged" in upgrade
    assert "docker manifest inspect" in upgrade
    assert "published API image" in upgrade
    assert "Skipping previous-release upgrade validation for the first published release baseline." in upgrade
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
