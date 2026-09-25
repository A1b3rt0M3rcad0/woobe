from __future__ import annotations

from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_workflow(name: str) -> dict:
    path = ROOT / ".github" / "workflows" / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def as_list(value):
    if isinstance(value, list):
        return value
    return [value]


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
    assert publish_steps.index("Preflight release version targets") < publish_steps.index(
        "Promote exact validated digests to release version"
    )

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
