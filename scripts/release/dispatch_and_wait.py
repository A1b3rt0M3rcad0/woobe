#!/usr/bin/env python3
"""Dispatch a GitHub Actions workflow and wait for that exact child run."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
import time
from typing import Any


class WorkflowDispatchError(RuntimeError):
    pass


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, check=False, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowDispatchError(
            f"command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def gh_json(args: list[str]) -> Any:
    return json.loads(run(["gh", *args]).stdout)


def write_output(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def parse_inputs(values: list[str]) -> list[str]:
    args: list[str] = []
    for value in values:
        if "=" not in value:
            raise WorkflowDispatchError(f"invalid --input {value!r}; expected key=value")
        args.extend(["-f", value])
    return args


def list_runs(repo: str, workflow: str) -> list[dict[str, Any]]:
    data = gh_json(
        [
            "api",
            "--method",
            "GET",
            f"repos/{repo}/actions/workflows/{workflow}/runs",
            "-f",
            "event=workflow_dispatch",
            "-f",
            "per_page=100",
        ]
    )
    return data.get("workflow_runs", [])


def find_run(
    repo: str,
    workflow: str,
    expected_title: str,
    not_before: datetime,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for item in list_runs(repo, workflow):
        if item.get("display_title") != expected_title:
            continue
        created_raw = item.get("created_at")
        if not created_raw:
            continue
        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        if created < not_before:
            continue
        matches.append(item)
    if not matches:
        return None
    return max(matches, key=lambda item: int(item["id"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--output-prefix", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = datetime.now(timezone.utc)
    # Allow small clock skew between the runner and GitHub's Actions API.
    # The orchestration_id embedded in the exact run title keeps this safe.
    not_before = started.replace(microsecond=0) - timedelta(seconds=10)

    dispatch = [
        "gh",
        "workflow",
        "run",
        args.workflow,
        "--repo",
        args.repo,
        "--ref",
        args.ref,
        *parse_inputs(args.input),
    ]
    run(dispatch)

    deadline = time.monotonic() + args.timeout_seconds
    child: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        child = find_run(args.repo, args.workflow, args.expected_title, not_before)
        if child is not None:
            break
        time.sleep(args.poll_seconds)

    if child is None:
        raise WorkflowDispatchError(
            f"timed out locating dispatched workflow {args.workflow!r} "
            f"with title {args.expected_title!r}"
        )

    run_id = str(child["id"])
    url = child.get("html_url") or (
        f"https://github.com/{args.repo}/actions/runs/{run_id}"
    )
    prefix = args.output_prefix
    write_output(args.github_output, f"{prefix}_run_id", run_id)
    write_output(args.github_output, f"{prefix}_url", url)
    print(f"Dispatched {args.workflow}: {url}")

    last = ""
    while time.monotonic() < deadline:
        current = gh_json(
            ["api", f"repos/{args.repo}/actions/runs/{run_id}"]
        )
        status = current.get("status") or "unknown"
        conclusion = current.get("conclusion") or ""
        snapshot = f"{status}/{conclusion}" if conclusion else status
        if snapshot != last:
            print(f"{args.workflow} #{run_id}: {snapshot}")
            last = snapshot
        if status == "completed":
            if conclusion != "success":
                raise WorkflowDispatchError(
                    f"{args.workflow} #{run_id} completed with {conclusion}: {url}"
                )
            return 0
        time.sleep(args.poll_seconds)

    raise WorkflowDispatchError(
        f"timed out waiting for {args.workflow} #{run_id}: {url}"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkflowDispatchError as exc:
        print(f"workflow dispatch error: {exc}", file=sys.stderr)
        raise SystemExit(1)
