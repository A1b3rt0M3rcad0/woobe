"""Resolve automatic Woobe releases without modifying Git, manifests or remote state."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def version_key(value: str) -> tuple:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid Semantic Version: {value}")
    numbers = tuple(int(match[i]) for i in (1, 2, 3))
    identifiers = []
    for item in (match[4] or "").split("."):
        if item.isdigit():
            if len(item) > 1 and item.startswith("0"):
                raise ValueError(f"Invalid numeric prerelease identifier: {value}")
            identifiers.append((0, int(item)))
        elif item:
            identifiers.append((1, item))
    return (*numbers, int(match[4] is None), tuple(identifiers))


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def git(*args: str) -> str:
    return command("git", *args)


def ancestor(older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], check=False
    )
    if result.returncode not in (0, 1):
        raise ValueError("Unable to determine release ancestry")
    return result.returncode == 0


def api_pages(repo: str, endpoint: str) -> list[dict]:
    # A 401/403/timeout is not evidence that a release or pending PR is absent.
    raw = command(
        "gh", "api", "--paginate", f"repos/{repo}/{endpoint}", "--jq", "@json"
    )
    pages = [json.loads(line) for line in raw.splitlines()]
    if not pages or any(
        not isinstance(page, list) or any(not isinstance(item, dict) for item in page)
        for page in pages
    ):
        raise ValueError("Unexpected paginated GitHub response")
    return [item for page in pages for item in page]


def published_releases(repo: str) -> dict[str, dict]:
    releases = {}
    for item in api_pages(repo, "releases?per_page=100"):
        tag = item["tag_name"]
        if item["draft"] or not tag.startswith("v"):
            continue
        try:
            version_key(tag[1:])
        except ValueError:
            continue
        if tag[1:] in releases:
            raise ValueError(f"Ambiguous published release {tag}")
        releases[tag[1:]] = item
    return releases


def released_revision(version: str) -> str:
    revision = git("rev-parse", f"refs/tags/v{version}^{{commit}}")
    if git("show", f"{revision}:VERSION").strip() != version:
        raise ValueError(f"Published v{version} does not contain its canonical VERSION")
    return revision


def bump(version: str, messages: str) -> str:
    major, minor, patch = version_key(version)[:3]
    commits = [message.strip() for message in messages.split("\0") if message.strip()]
    breaking = any(
        re.match(r"^[A-Za-z][A-Za-z0-9_-]*(?:\([^\n)]+\))?!:", message)
        or re.search(r"(?m)^BREAKING[ -]CHANGE:", message)
        for message in commits
    )
    feature = any(re.match(r"^feat(?:\([^\n)]+\))?:", message) for message in commits)
    if breaking and major:
        return f"{major + 1}.0.0"
    if breaking or feature:
        return f"{major}.{minor + 1}.0"
    if SEMVER.fullmatch(version)[4] is not None:
        return f"{major}.{minor}.{patch}"
    return f"{major}.{minor}.{patch + 1}"


def next_version(current: str, releases: dict[str, dict], revision: str) -> str:
    if not releases:
        return bump(current, git("log", "-1", "--format=%B", revision))
    latest = max(releases, key=version_key)
    previous = released_revision(latest)
    if not ancestor(previous, revision):
        raise ValueError("Current master does not include the latest published release")
    proposed = bump(latest, git("log", "--format=%B%x00", f"{previous}..{revision}"))
    return max((current, proposed), key=version_key)


def selection(
    version: str, releases: dict[str, dict], *, skip=False, reason=""
) -> dict[str, str]:
    record = releases.get(version)
    has_manifest = bool(
        record
        and any(asset["name"] == "release-manifest.json" for asset in record["assets"])
    )
    return {
        "version": version,
        "skip": str(skip).lower(),
        "reason": reason,
        "release_exists": str(record is not None).lower(),
        "already_published": str(has_manifest).lower(),
    }


def resolve(
    repo: str, requested="", source="", event="workflow_dispatch"
) -> dict[str, str]:
    head = git("rev-parse", "HEAD")
    if not ancestor(head, "origin/master"):
        raise ValueError("Automatic release must use reviewed master")
    current = git("show", f"{head}:VERSION").strip()
    version_key(current)
    if source and not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Source must be a complete lowercase commit SHA")
    if event == "push" and source != head:
        return selection(
            current, {}, skip=True, reason="A newer master push superseded this source"
        )
    releases = published_releases(repo)
    if requested:
        version_key(requested)
        return selection(requested, releases, reason="Explicit release or recovery")

    # Repair an incomplete permanent release before reserving another version.
    if (
        current in releases
        and selection(current, releases)["already_published"] != "true"
    ):
        return selection(
            current, releases, reason="Repair the incomplete permanent release record"
        )

    pending = []
    for item in api_pages(repo, "pulls?state=open&base=master&per_page=100"):
        if (
            item["base"]["ref"] != "master"
            or not item["head"]["repo"]
            or item["head"]["repo"]["full_name"].lower() != repo.lower()
        ):
            continue
        branch = item["head"]["ref"]
        if branch.startswith("release/"):
            target = branch.removeprefix("release/")
            version_key(target)
            if version_key(target) <= version_key(current):
                raise ValueError(
                    "An obsolete open release PR needs operator inspection"
                )
            pending.append(target)
    if len(pending) > 1:
        raise ValueError(
            "Multiple open release PRs; resolve the ambiguity before publication"
        )
    if pending:
        return selection(pending[0], releases, reason="Resume the existing release PR")

    if releases:
        latest = max(releases, key=version_key)
        if version_key(current) < version_key(latest):
            raise ValueError(
                "Canonical VERSION is older than the latest published release"
            )
        if version_key(current) > version_key(latest):
            return selection(
                current, releases, reason="Resume exact post-merge release finalization"
            )
        if ancestor(head, released_revision(latest)):
            return selection(
                current,
                releases,
                skip=True,
                reason="This source is already included in the published release",
            )
    target = next_version(current, releases, head)
    return selection(
        target,
        releases,
        reason="Calculate the next version from reviewed Conventional Commits",
    )


def verify_coverage(repo: str, target: str) -> None:
    version_key(target)
    current = git("show", "origin/master:VERSION").strip()
    releases = published_releases(repo)
    required = next_version(current, releases, git("rev-parse", "origin/master"))
    if version_key(target) < version_key(required):
        raise ValueError(
            f"Concurrent master changes require {required}, not {target}; inspect the release PR before retrying"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        required=not os.environ.get("GITHUB_REPOSITORY"),
    )
    parser.add_argument("--version", default="")
    parser.add_argument("--source", default="")
    parser.add_argument(
        "--event", choices=("push", "workflow_dispatch"), default="workflow_dispatch"
    )
    parser.add_argument("--verify-version", default="")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("Invalid owner/repository")
    if args.verify_version:
        verify_coverage(args.repo, args.verify_version)
        return
    result = resolve(args.repo, args.version, args.source, args.event)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            for key, value in result.items():
                output.write(f"{key}={value}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
