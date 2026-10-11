from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_workflow(name: str) -> dict:
    path = ROOT / ".github" / "workflows" / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def as_list(value):
    if isinstance(value, list):
        return value
    return [value]


@pytest.mark.parametrize("workflow", ["prepare-release.yml", "release-candidate.yml", "release.yml"])
def test_release_jobs_use_isolated_github_hosted_runners_and_cleanup_docker(workflow: str) -> None:
    for name, job in load_workflow(workflow)["jobs"].items():
        if "uses" in job:
            continue
        assert job["runs-on"] == "ubuntu-24.04", name
        steps = job["steps"]
        docker_actions = [i for i, step in enumerate(steps) if step.get("uses", "").startswith("docker/")]
        if not docker_actions:
            # In particular, a job waiting for required CI should not need
            # Docker access, even on an isolated VM.
            assert not any("prepare_docker_access" in step.get("run", "") for step in steps)
            continue
        names = [step.get("name") for step in steps]
        assert names.index("Prepare private release Docker configuration") < names.index("Prepare Docker access") < min(docker_actions)
        assert int(job["timeout-minutes"]) >= 75  # Retain the full release build and smoke budget.
        assert steps[-1]["name"] == "Clean up release Docker resources"
        assert steps[-1]["if"] == "always()"
        assert any(step.get("uses", "").startswith("actions/checkout@") for step in steps)
        for step in steps:
            if step.get("uses", "").startswith("docker/setup-buildx-action@"):
                assert step["with"]["cleanup"] == "false"
                assert step["id"] == "release_buildx"
                assert "steps.release_buildx.outputs.name" in steps[-1]["env"]["WOOBE_RELEASE_BUILDER"]
            if step.get("uses", "").startswith("docker/login-action@"):
                assert step["with"]["logout"] == "false"
    if workflow == "release-candidate.yml":
        assert load_workflow(workflow)["jobs"]["build"]["strategy"]["max-parallel"] == "4"


def test_github_hosted_docker_prepare_checks_daemon_without_shared_lock(tmp_path: Path) -> None:
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o700)
    env = {
        **os.environ,
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_TEMP": str(tmp_path),
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
    }
    command = ["bash", "scripts/ci/prepare_docker_access.sh"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "no shared host lock required" in result.stdout
    assert not list(tmp_path.glob("woobe-docker-lock-*"))

    docker.write_text("#!/bin/sh\nexit 1\n")
    failed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "Docker is unavailable" in failed.stdout


@pytest.mark.parametrize("docker_exit", [0, 1])
def test_release_docker_credentials_are_private_and_cleanup_survives_failure(tmp_path: Path, docker_exit: int) -> None:
    original = tmp_path / "original"
    plugins = original / "cli-plugins"
    plugins.mkdir(parents=True)
    (original / "config.json").write_text('{"auths":{"existing":"private"}}')
    (plugins / "docker-compose").write_text("plugin")
    environment_file = tmp_path / "environment"
    env = {**os.environ, "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_TEMP": str(tmp_path), "GITHUB_ENV": str(environment_file), "DOCKER_CONFIG": str(original)}
    subprocess.run(["bash", "scripts/release/prepare_docker_config.sh"], cwd=ROOT, env=env, check=True)
    env.update(dict(line.split("=", 1) for line in environment_file.read_text().splitlines()))
    private = Path(env["DOCKER_CONFIG"])
    assert private != original
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "cli-plugins/docker-compose").read_text() == "plugin"
    assert not (private / "config.json").exists()
    (private / "config.json").write_text("issued registry credential")
    # Even a failed builder removal must remove the job's credentials and
    # clean up any legacy lock state, preserving unrelated credentials.
    docker = tmp_path / "docker"
    docker.write_text(f"#!/bin/sh\nexit {docker_exit}\n")
    docker.chmod(0o700)
    release_file = tmp_path / "release-lock"
    acquired_file = tmp_path / "acquired-lock"
    acquired_file.touch()
    env.update({"PATH": f"{tmp_path}:{env['PATH']}", "WOOBE_RELEASE_BUILDER": "owned-builder", "WOOBE_DOCKER_LOCK_RELEASE_FILE": str(release_file), "WOOBE_DOCKER_LOCK_ACQUIRED_FILE": str(acquired_file)})
    result = subprocess.run(["bash", "scripts/release/cleanup_docker.sh"], cwd=ROOT, env=env, capture_output=True)
    assert result.returncode == docker_exit
    assert not private.exists()
    assert not acquired_file.exists()
    assert (original / "config.json").read_text() == '{"auths":{"existing":"private"}}'


def test_release_cleanup_refuses_unrelated_configuration(tmp_path: Path) -> None:
    original = tmp_path / "unrelated"
    original.mkdir()
    (original / "config.json").write_text("keep")
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o700)
    env = {**os.environ, "RUNNER_TEMP": str(tmp_path), "WOOBE_RELEASE_DOCKER_CONFIG": str(original), "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    result = subprocess.run(["bash", "scripts/release/cleanup_docker.sh"], cwd=ROOT, env=env, capture_output=True)
    assert result.returncode != 0
    assert (original / "config.json").read_text() == "keep"


def test_release_workflow_graph_is_parent_owned_and_serial() -> None:
    prepare = load_workflow("prepare-release.yml")
    jobs = prepare["jobs"]

    assert set(jobs) >= {
        "prepare",
        "candidate",
        "publish",
        "verify-published",
        "summary",
    }
    assert "tag" not in jobs

    assert jobs["candidate"]["needs"] == "prepare"
    assert jobs["candidate"]["uses"] == "./.github/workflows/release-candidate.yml"

    assert set(as_list(jobs["publish"]["needs"])) == {"prepare", "candidate"}
    assert jobs["publish"]["uses"] == "./.github/workflows/release.yml"

    assert jobs["verify-published"]["needs"] == "prepare"
    assert set(as_list(jobs["summary"]["needs"])) == {
        "identity",
        "prepare",
        "candidate",
        "publish",
        "verify-published",
    }

    release = load_workflow("release.yml")
    release_jobs = release["jobs"]
    assert set(release_jobs) >= {
        "publish",
        "post-publish-smoke",
        "tag",
        "github-release",
    }
    assert release_jobs["post-publish-smoke"]["needs"] == "publish"
    assert set(as_list(release_jobs["tag"]["needs"])) == {
        "publish",
        "post-publish-smoke",
    }
    assert set(as_list(release_jobs["github-release"]["needs"])) == {
        "publish",
        "post-publish-smoke",
        "tag",
    }

    publish_steps = [
        step.get("name")
        for step in release_jobs["publish"]["steps"]
        if step.get("name")
    ]
    assert publish_steps.index(
        "Preflight release version targets"
    ) < publish_steps.index("Promote exact validated digests to release version")

    assert prepare["concurrency"]["cancel-in-progress"] == "false"
    assert prepare["permissions"]["packages"] == "write"


def test_candidate_returns_digests_without_actions_artifact_transport() -> None:
    candidate = load_workflow("release-candidate.yml")
    triggers = candidate["on"]
    assert set(triggers) == {"workflow_call", "workflow_dispatch"}

    outputs = triggers["workflow_call"]["outputs"]
    assert set(outputs) == {
        "validation_id",
        "api_digest",
        "workers_digest",
        "frontend_digest",
        "embed_digest",
    }

    manifest_outputs = candidate["jobs"]["manifest"]["outputs"]
    assert set(manifest_outputs) == set(outputs)

    raw = (ROOT / ".github/workflows/release-candidate.yml").read_text(encoding="utf-8")
    assert "actions/upload-artifact" not in raw
    assert candidate["concurrency"]["cancel-in-progress"] == "false"


def test_publisher_has_no_independent_trigger_or_rebuild_path() -> None:
    release = load_workflow("release.yml")
    assert set(release["on"]) == {"workflow_call"}

    required_inputs = {
        "version",
        "revision",
        "validation_id",
        "api_digest",
        "workers_digest",
        "frontend_digest",
        "embed_digest",
        "orchestration_id",
    }
    assert set(release["on"]["workflow_call"]["inputs"]) == required_inputs

    raw = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "docker/build-push-action" not in raw
    assert "push:" not in raw.split("permissions:", 1)[0]
    assert "release-manifest.json" in raw
    assert release["concurrency"]["cancel-in-progress"] == "false"


def test_release_recovery_verifies_terminal_state_before_success() -> None:
    prepare = (ROOT / ".github/workflows/prepare-release.yml").read_text(
        encoding="utf-8"
    )

    assert "Verify completed release recovery" in prepare
    assert "release-manifest.json" in prepare
    assert "EXPECTED_API_DIGEST" in prepare
    assert "linux/amd64" in prepare
    assert "linux/arm64" in prepare
    assert "Complete pending release branch cleanup" in prepare
    assert "exists without release-manifest.json" in prepare


def test_release_target_resolution_shell_is_syntactically_valid() -> None:
    prepare = load_workflow("prepare-release.yml")
    step = next(
        step
        for step in prepare["jobs"]["prepare"]["steps"]
        if step.get("name") == "Validate target version and resolve release state"
    )

    result = subprocess.run(
        ["bash", "-n"],
        input=step["run"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "passes"),
    [
        ({}, True),
        ({"CANDIDATE_RESULT": "failure"}, False),
        ({"PUBLISH_RESULT": "cancelled"}, False),
        ({"IDENTITY_RESULT": "failure"}, False),
        ({"ALREADY_PUBLISHED": "true", "VERIFY_RESULT": "failure"}, False),
        ({"ALREADY_PUBLISHED": "true", "VERIFY_RESULT": "success"}, True),
        (
            {
                "SKIP_RELEASE": "true",
                "PREPARE_RESULT": "skipped",
                "CANDIDATE_RESULT": "skipped",
                "PUBLISH_RESULT": "skipped",
            },
            True,
        ),
        ({"SKIP_RELEASE": "true"}, False),
    ],
)
def test_terminal_gate_distinguishes_publication_recovery_and_skip(overrides, passes):
    step = next(
        step
        for step in load_workflow("prepare-release.yml")["jobs"]["summary"]["steps"]
        if step.get("name") == "Validate terminal orchestration state"
    )
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "IDENTITY_RESULT": "success",
            "SKIP_RELEASE": "false",
            "ALREADY_PUBLISHED": "false",
            "PREPARE_RESULT": "success",
            "CANDIDATE_RESULT": "success",
            "PUBLISH_RESULT": "success",
            "VERIFY_RESULT": "skipped",
            **overrides,
        },
    )
    assert (result.returncode == 0) == passes
