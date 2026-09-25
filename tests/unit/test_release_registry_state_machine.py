from __future__ import annotations

import os
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]


def workflow_step_script(workflow_name: str, job_name: str, step_name: str) -> str:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    for step in workflow["jobs"][job_name]["steps"]:
        if step.get("name") == step_name:
            return step["run"]
    raise AssertionError(
        f"step {step_name!r} not found in {workflow_name}:{job_name}"
    )


FAKE_DOCKER = r"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
scenario = os.environ["FAKE_DOCKER_SCENARIO"]
log = Path(os.environ["FAKE_DOCKER_LOG"])
state_dir = Path(os.environ["FAKE_DOCKER_STATE"])
state_dir.mkdir(parents=True, exist_ok=True)

with log.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\n")


def unit_from_ref(ref: str) -> str:
    for unit in ("api", "workers", "frontend", "embed"):
        if f"woobe-{unit}:" in ref or f"woobe-{unit}@" in ref:
            return unit
    raise SystemExit(f"unable to identify unit from {ref}")


def expected(unit: str) -> str:
    return os.environ.get(f"{unit.upper()}_DIGEST", f"sha256:{unit}")


if args[:3] == ["buildx", "imagetools", "inspect"]:
    ref = args[-1]

    if scenario == "candidate_exists":
        print("Digest: sha256:candidate")
        raise SystemExit(0)

    if scenario == "candidate_missing":
        print("manifest unknown", file=sys.stderr)
        raise SystemExit(1)

    if scenario == "candidate_transient":
        print("unexpected status: 503 Service Unavailable", file=sys.stderr)
        raise SystemExit(1)

    unit = unit_from_ref(ref)

    if scenario == "publish_unknown":
        print("unexpected status: 503 Service Unavailable", file=sys.stderr)
        raise SystemExit(1)

    if scenario == "publish_conflict":
        if unit == "api":
            print("Digest: sha256:conflict")
        else:
            print(f"Digest: {expected(unit)}")
        raise SystemExit(0)

    if scenario == "publish_partial":
        marker = state_dir / f"published-{unit}"
        if unit in {"api", "frontend"} or marker.exists():
            print(f"Digest: {expected(unit)}")
            raise SystemExit(0)
        print("manifest unknown", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(f"unsupported inspect scenario: {scenario}")

if args[:3] == ["buildx", "imagetools", "create"]:
    tag = args[args.index("--tag") + 1]
    unit = unit_from_ref(tag)
    (state_dir / f"published-{unit}").write_text("1", encoding="utf-8")
    raise SystemExit(0)

raise SystemExit(f"unsupported fake docker command: {args}")
"""


FAKE_GIT = r"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log = Path(os.environ["FAKE_GIT_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\n")

if args[:3] == ["ls-remote", "--exit-code", "--heads"]:
    raise SystemExit(0)

if args[:3] == ["push", "origin", "--delete"]:
    raise SystemExit(0)

raise SystemExit(f"unsupported fake git command: {args}")
"""


def make_fake_bin(tmp_path: Path, *, docker: bool = True, git: bool = False) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)

    if docker:
        docker_path = fake_bin / "docker"
        docker_path.write_text(FAKE_DOCKER, encoding="utf-8")
        docker_path.chmod(0o755)

    if git:
        git_path = fake_bin / "git"
        git_path.write_text(FAKE_GIT, encoding="utf-8")
        git_path.chmod(0o755)

    sleep_path = fake_bin / "sleep"
    sleep_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    sleep_path.chmod(0o755)
    return fake_bin


def run_step(
    script: str,
    tmp_path: Path,
    *,
    scenario: str | None = None,
    extra_env: dict[str, str] | None = None,
    fake_git: bool = False,
) -> subprocess.CompletedProcess[str]:
    fake_bin = make_fake_bin(tmp_path, docker=scenario is not None, git=fake_git)
    output = tmp_path / "github-output"
    docker_log = tmp_path / "docker.log"
    docker_state = tmp_path / "docker-state"
    git_log = tmp_path / "git.log"

    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "FAKE_DOCKER_LOG": str(docker_log),
        "FAKE_DOCKER_STATE": str(docker_state),
        "FAKE_GIT_LOG": str(git_log),
    }
    if scenario is not None:
        env["FAKE_DOCKER_SCENARIO"] = scenario
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def publish_env() -> dict[str, str]:
    return {
        "OWNER": "owner",
        "VERSION": "0.12.0",
        "API_DIGEST": "sha256:111",
        "WORKERS_DIGEST": "sha256:222",
        "FRONTEND_DIGEST": "sha256:333",
        "EMBED_DIGEST": "sha256:444",
    }


def test_candidate_probe_reuses_existing_candidate(tmp_path: Path) -> None:
    script = workflow_step_script(
        "release-candidate.yml", "build", "Probe immutable candidate"
    )
    result = run_step(script, tmp_path, scenario="candidate_exists")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "github-output").read_text(encoding="utf-8") == "state=exists\n"


def test_candidate_probe_builds_only_on_explicit_missing(tmp_path: Path) -> None:
    script = workflow_step_script(
        "release-candidate.yml", "build", "Probe immutable candidate"
    )
    result = run_step(script, tmp_path, scenario="candidate_missing")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "github-output").read_text(encoding="utf-8") == "state=missing\n"


def test_candidate_probe_fails_closed_after_transient_registry_errors(
    tmp_path: Path,
) -> None:
    script = workflow_step_script(
        "release-candidate.yml", "build", "Probe immutable candidate"
    )
    result = run_step(script, tmp_path, scenario="candidate_transient")

    assert result.returncode != 0
    assert "Unable to determine whether immutable candidate exists" in result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert log.count("buildx imagetools inspect") == 5


def test_partial_publication_resumes_without_overwriting_existing_tags(
    tmp_path: Path,
) -> None:
    script = workflow_step_script(
        "release.yml", "publish", "Promote exact validated digests to release version"
    )
    result = run_step(
        script,
        tmp_path,
        scenario="publish_partial",
        extra_env=publish_env(),
    )

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    create_lines = [
        line
        for line in log.splitlines()
        if line.startswith("buildx imagetools create ")
    ]
    assert len(create_lines) == 2
    assert any("woobe-workers:0.12.0" in line for line in create_lines)
    assert any("woobe-embed:0.12.0" in line for line in create_lines)
    assert not any("woobe-api:0.12.0" in line for line in create_lines)
    assert not any("woobe-frontend:0.12.0" in line for line in create_lines)


def test_existing_conflicting_release_digest_blocks_publication(tmp_path: Path) -> None:
    script = workflow_step_script(
        "release.yml", "publish", "Promote exact validated digests to release version"
    )
    result = run_step(
        script,
        tmp_path,
        scenario="publish_conflict",
        extra_env=publish_env(),
    )

    assert result.returncode != 0
    assert "Immutable release image already exists with a different digest" in (
        result.stdout + result.stderr
    )
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "buildx imagetools create" not in log


def test_unknown_release_registry_state_never_authorizes_promotion(
    tmp_path: Path,
) -> None:
    script = workflow_step_script(
        "release.yml", "publish", "Promote exact validated digests to release version"
    )
    result = run_step(
        script,
        tmp_path,
        scenario="publish_unknown",
        extra_env=publish_env(),
    )

    assert result.returncode != 0
    assert "Registry state is unknown" in (result.stdout + result.stderr)
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert log.count("woobe-api:0.12.0") == 5
    assert "buildx imagetools create" not in log


def test_completed_release_recovery_removes_leftover_release_branch(
    tmp_path: Path,
) -> None:
    script = workflow_step_script(
        "prepare-release.yml",
        "verify-published",
        "Complete pending release branch cleanup",
    )
    result = run_step(
        script,
        tmp_path,
        extra_env={"VERSION": "0.12.0"},
        fake_git=True,
    )

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "git.log").read_text(encoding="utf-8")
    assert "ls-remote --exit-code --heads origin release/0.12.0" in log
    assert "push origin --delete release/0.12.0" in log
