#!/usr/bin/env python3
"""Drive the release PR from validation through an exact, gated merge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REQUIRED_WORKFLOWS: dict[str, str] = {
    "Backend test suite": "tests.yml",
    "Frontend test and build": "frontend.yml",
    "Package Build": "package-build.yml",
    "Acceptance": "acceptance.yml",
    "Quality Gate": "quality-gate.yml",
    "Container quality": "containers.yml",
    "Security audit": "security.yml",
    "CLA acceptance": "cla.yml",
}

ALLOWED_RELEASE_PATHS = {
    "VERSION",
    "pyproject.toml",
    "uv.lock",
    "packages/woobe-core/pyproject.toml",
    "packages/woobe-api/pyproject.toml",
    "packages/woobe-workers/pyproject.toml",
    "packages/woobe-runtime-client/package.json",
    "packages/woobe-ui/package.json",
    "packages/woobe-frontend/package.json",
    "packages/woobe-frontend/package-lock.json",
    "packages/woobe-embed/package.json",
    "packages/woobe-embed/package-lock.json",
    "packages/woobe-api/src/main.py",
    "packages/woobe-core/src/modules/agent/application/mcp_discovery.py",
    "packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py",
}

SUCCESS = "success"


class ReleaseGateError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=capture,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ReleaseGateError(
            f"command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def gh_json(args: list[str]) -> Any:
    result = run(["gh", *args])
    return json.loads(result.stdout)


def repo_api(repo: str, path: str) -> Any:
    return gh_json(["api", f"repos/{repo}/{path}"])


def pr(repo: str, number: int) -> dict[str, Any]:
    return repo_api(repo, f"pulls/{number}")


def comment(repo: str, number: int, body: str) -> None:
    result = run(
        ["gh", "pr", "comment", str(number), "--repo", repo, "--body", body],
        check=False,
    )
    if result.returncode != 0:
        print(
            "warning: unable to post release-gate comment: "
            + (result.stderr or result.stdout).strip(),
            file=sys.stderr,
        )


def fail(repo: str, number: int, message: str) -> None:
    comment(
        repo,
        number,
        "<!-- woobe-release-gate -->\n"
        "## Release blocked\n\n"
        f"{message}\n\n"
        "Nothing was merged, tagged, or published.",
    )
    raise ReleaseGateError(message)


def git_output(args: list[str]) -> str:
    return run(["git", *args]).stdout.strip()


def checkout_release_branch(repo: str, number: int, branch: str, version: str) -> str:
    data = pr(repo, number)
    if data["state"] != "open":
        fail(repo, number, f"Release PR is not open (state={data['state']}).")
    if data["head"]["ref"] != branch:
        fail(
            repo,
            number,
            f"Unexpected release branch: {data['head']['ref']} (expected {branch}).",
        )
    if data["head"]["repo"]["full_name"] != repo:
        fail(repo, number, "Release PR head must belong to the Woobe repository.")

    run(["git", "fetch", "--force", "origin"], capture=False)
    run(["git", "checkout", "-B", branch, f"origin/{branch}"], capture=False)

    current = Path("VERSION").read_text(encoding="utf-8").strip()
    if current != version:
        fail(
            repo,
            number,
            f"Canonical VERSION is {current}, but the requested release is {version}.",
        )

    run([sys.executable, "scripts/ci/check_package_versions.py"], capture=False)

    files = run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/pulls/{number}/files",
            "--jq",
            ".[].filename",
        ]
    ).stdout.splitlines()
    unexpected = sorted(set(files) - ALLOWED_RELEASE_PATHS)
    if unexpected:
        rendered = "\n".join(f"- `{path}`" for path in unexpected)
        fail(
            repo,
            number,
            "Release PR contains non-release-preparation files:\n\n" + rendered,
        )

    return git_output(["rev-parse", "HEAD"])


def refresh_from_master_if_needed(
    repo: str,
    number: int,
    branch: str,
    version: str,
) -> tuple[str, bool]:
    run(["git", "fetch", "--force", "origin"], capture=False)
    master_sha = git_output(["rev-parse", "origin/master"])
    head_sha = git_output(["rev-parse", f"origin/{branch}"])

    ancestor = run(
        ["git", "merge-base", "--is-ancestor", master_sha, head_sha],
        check=False,
    )
    if ancestor.returncode == 0:
        return head_sha, False

    print(
        f"master advanced to {master_sha}; refreshing {branch} and requiring a new CI pass."
    )
    run(["git", "checkout", "-B", branch, f"origin/{branch}"], capture=False)
    merge = run(["git", "merge", "--no-edit", "origin/master"], check=False, capture=False)
    if merge.returncode != 0:
        run(["git", "merge", "--abort"], check=False, capture=False)
        fail(
            repo,
            number,
            "master advanced and could not be merged cleanly into the release branch. "
            "Resolve the conflict before retrying the release.",
        )

    current = Path("VERSION").read_text(encoding="utf-8").strip()
    if current != version:
        fail(
            repo,
            number,
            f"Refreshing from master changed VERSION to {current}; expected {version}.",
        )
    run([sys.executable, "scripts/ci/check_package_versions.py"], capture=False)
    run(["git", "push", "origin", branch], capture=False)
    return git_output(["rev-parse", "HEAD"]), True


def workflow_runs(repo: str, head_sha: str) -> dict[str, dict[str, Any]]:
    data = gh_json(
        [
            "api",
            "--method",
            "GET",
            f"repos/{repo}/actions/runs",
            "-f",
            f"head_sha={head_sha}",
            "-f",
            "per_page=100",
        ]
    )
    latest: dict[str, dict[str, Any]] = {}
    for item in data.get("workflow_runs", []):
        name = item.get("name")
        if name not in REQUIRED_WORKFLOWS:
            continue
        current = latest.get(name)
        if current is None or item.get("created_at", "") > current.get("created_at", ""):
            latest[name] = item
    return latest


def dispatch_missing(
    repo: str,
    number: int,
    branch: str,
    head_sha: str,
) -> None:
    # Give pull_request-triggered runs a short window to appear before using
    # workflow_dispatch as a deterministic fallback.
    grace_deadline = time.monotonic() + 20
    latest: dict[str, dict[str, Any]] = {}
    while time.monotonic() < grace_deadline:
        latest = workflow_runs(repo, head_sha)
        if len(latest) == len(REQUIRED_WORKFLOWS):
            return
        time.sleep(5)

    for name, workflow in REQUIRED_WORKFLOWS.items():
        if name in latest:
            continue
        print(f"No {name} run appeared for {head_sha}; dispatching {workflow}.")
        args = [
            "workflow",
            "run",
            workflow,
            "--repo",
            repo,
            "--ref",
            branch,
        ]
        if workflow == "cla.yml":
            args += ["-f", f"pr_number={number}"]
        run(["gh", *args], capture=False)


def render_status(latest: dict[str, dict[str, Any]]) -> str:
    lines = []
    for name in REQUIRED_WORKFLOWS:
        item = latest.get(name)
        if item is None:
            lines.append(f"- {name}: missing")
            continue
        status = item.get("status") or "unknown"
        conclusion = item.get("conclusion")
        suffix = f"/{conclusion}" if conclusion else ""
        url = item.get("html_url")
        if url:
            lines.append(f"- {name}: {status}{suffix} ({url})")
        else:
            lines.append(f"- {name}: {status}{suffix}")
    return "\n".join(lines)


def wait_for_green(
    repo: str,
    number: int,
    branch: str,
    head_sha: str,
    timeout_seconds: int,
) -> None:
    dispatch_missing(repo, number, branch, head_sha)
    deadline = time.monotonic() + timeout_seconds
    last_snapshot = ""

    while time.monotonic() < deadline:
        latest = workflow_runs(repo, head_sha)
        snapshot = render_status(latest)
        if snapshot != last_snapshot:
            print(snapshot)
            last_snapshot = snapshot

        if len(latest) < len(REQUIRED_WORKFLOWS):
            time.sleep(15)
            continue

        incomplete = [
            name
            for name, item in latest.items()
            if item.get("status") != "completed"
        ]
        if incomplete:
            time.sleep(15)
            continue

        failed = {
            name: item
            for name, item in latest.items()
            if item.get("conclusion") != SUCCESS
        }
        if failed:
            fail(
                repo,
                number,
                "Required CI did not pass for release head "
                f"`{head_sha}`.\n\n{render_status(latest)}",
            )

        print(f"All required release checks passed for {head_sha}.")
        return

    latest = workflow_runs(repo, head_sha)
    fail(
        repo,
        number,
        "Timed out waiting for required release CI.\n\n" + render_status(latest),
    )


def merge_release(
    repo: str,
    number: int,
    head_sha: str,
    version: str,
) -> str:
    latest = pr(repo, number)
    if latest["head"]["sha"] != head_sha:
        fail(
            repo,
            number,
            "Release PR head changed after validation; a new CI pass is required.",
        )

    result = run(
        [
            "gh",
            "pr",
            "merge",
            str(number),
            "--repo",
            repo,
            "--merge",
            "--match-head-commit",
            head_sha,
        ],
        check=False,
        capture=False,
    )
    if result.returncode != 0:
        fail(
            repo,
            number,
            "All release CI passed, but GitHub rejected the automated merge. "
            "Check branch protection/review requirements and retry.",
        )

    merged = pr(repo, number)
    if not merged.get("merged"):
        fail(repo, number, "GitHub did not report the release PR as merged.")

    merge_sha = merged.get("merge_commit_sha")
    if not merge_sha:
        fail(repo, number, "Merged release PR did not expose a merge commit SHA.")

    run(["git", "fetch", "--force", "origin"], capture=False)
    merged_version = git_output(["show", f"{merge_sha}:VERSION"]).strip()
    if merged_version != version:
        fail(
            repo,
            number,
            f"Merged release commit contains VERSION={merged_version}; expected {version}.",
        )

    return merge_sha


def write_outputs(path: str | None, values: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=10_800)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.repo:
        raise ReleaseGateError("--repo or GITHUB_REPOSITORY is required")

    max_validation_cycles = 5
    validated_head = ""

    for cycle in range(1, max_validation_cycles + 1):
        print(f"Release validation cycle {cycle}/{max_validation_cycles}")
        checked_head = checkout_release_branch(
            args.repo,
            args.pr,
            args.branch,
            args.version,
        )
        refreshed_head, refreshed = refresh_from_master_if_needed(
            args.repo,
            args.pr,
            args.branch,
            args.version,
        )
        head_sha = refreshed_head if refreshed else checked_head

        wait_for_green(
            args.repo,
            args.pr,
            args.branch,
            head_sha,
            args.timeout_seconds,
        )

        # Protect the merge from both a new PR-head commit and a moving master.
        latest_pr = pr(args.repo, args.pr)
        if latest_pr["head"]["sha"] != head_sha:
            print("Release PR head changed while CI was running; validating the new head.")
            continue

        refreshed_head, refreshed = refresh_from_master_if_needed(
            args.repo,
            args.pr,
            args.branch,
            args.version,
        )
        if refreshed:
            print(
                "master advanced after CI passed; release branch refreshed and will be revalidated."
            )
            continue

        validated_head = refreshed_head
        break
    else:
        fail(
            args.repo,
            args.pr,
            "Release could not reach a stable, fully validated head after "
            f"{max_validation_cycles} validation cycles.",
        )

    merge_sha = merge_release(
        args.repo,
        args.pr,
        validated_head,
        args.version,
    )
    comment(
        args.repo,
        args.pr,
        "<!-- woobe-release-gate -->\n"
        "## Release gate passed\n\n"
        f"All required CI passed for `{validated_head}`.\n\n"
        f"Merged as `{merge_sha}`. Release finalization is continuing automatically.",
    )
    write_outputs(
        args.github_output,
        {
            "validated_head_sha": validated_head,
            "merge_sha": merge_sha,
        },
    )
    print(f"Release PR merged successfully: {merge_sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        print(f"release gate error: {exc}", file=sys.stderr)
        raise SystemExit(1)
