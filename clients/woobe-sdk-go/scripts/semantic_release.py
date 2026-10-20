#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import re
import subprocess
from pathlib import Path
from typing import Iterable

SEMVER_RE = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)
CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[A-Za-z0-9_-]+)(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?:\s*(?P<description>.+)$"
)
BREAKING_FOOTER_RE = re.compile(
    r"(?im)^BREAKING(?: |-)?CHANGE:\s*.+$"
)

KNOWN_TYPES = {
    "feat",
    "fix",
    "perf",
    "refactor",
    "docs",
    "test",
    "tests",
    "ci",
    "build",
    "chore",
    "style",
    "revert",
}

BUMP_PRIORITY = {"patch": 1, "minor": 2, "major": 3}


@dataclasses.dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str = ""


@dataclasses.dataclass(frozen=True)
class ClassifiedCommit:
    commit: Commit
    commit_type: str
    description: str
    breaking: bool
    bump: str


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def next_version(version: tuple[int, int, int], bump: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump == "major":
        return major + 1, 0, 0
    if bump == "minor":
        return major, minor + 1, 0
    if bump == "patch":
        return major, minor, patch + 1
    raise ValueError(f"unsupported bump: {bump}")


def classify_commit(commit: Commit) -> ClassifiedCommit:
    match = CONVENTIONAL_RE.fullmatch(commit.subject.strip())
    if match:
        raw_type = match.group("type").lower()
        commit_type = raw_type if raw_type in KNOWN_TYPES else "chore"
        description = match.group("description").strip()
        breaking = bool(match.group("breaking"))
    else:
        commit_type = "chore"
        description = commit.subject.strip()
        breaking = False

    breaking = breaking or bool(BREAKING_FOOTER_RE.search(commit.body))
    bump = "major" if breaking else "minor" if commit_type == "feat" else "patch"
    return ClassifiedCommit(
        commit=commit,
        commit_type=commit_type,
        description=description,
        breaking=breaking,
        bump=bump,
    )


def highest_bump(commits: Iterable[ClassifiedCommit]) -> str:
    winner = "patch"
    for commit in commits:
        if BUMP_PRIORITY[commit.bump] > BUMP_PRIORITY[winner]:
            winner = commit.bump
    return winner


def list_stable_tags() -> list[tuple[tuple[int, int, int], str]]:
    tags = run_git("tag", "--merged", "HEAD", "--list", "v[0-9]*").splitlines()
    parsed = []
    for tag in tags:
        version = parse_version(tag)
        if version is not None:
            parsed.append((version, tag))
    return sorted(parsed)


def tag_points_at_head(tag: str) -> bool:
    return run_git("rev-parse", f"{tag}^{{commit}}") == run_git("rev-parse", "HEAD")


def load_commits(revision_range: str | None) -> list[Commit]:
    args = ["log", "--no-merges", "--reverse", "--format=%H%x1f%s%x1f%b%x1e"]
    if revision_range:
        args.append(revision_range)
    raw = run_git(*args)
    if not raw:
        return []

    commits: list[Commit] = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x1f", 2)
        if len(parts) < 2:
            continue
        sha = parts[0].strip()
        subject = parts[1].strip()
        body = parts[2].strip() if len(parts) == 3 else ""
        commits.append(Commit(sha=sha, subject=subject, body=body))
    return commits


def notes_for(
    version: str,
    previous_tag: str | None,
    commits: list[ClassifiedCommit],
    bump: str,
) -> str:
    baseline = previous_tag or "repository start"
    lines = [
        f"# Woobe SDK for Go v{version}",
        "",
        f"Semantic bump: **{bump}**",
        f"Changes since: **{baseline}**",
        "",
    ]

    groups: list[tuple[str, list[ClassifiedCommit]]] = [
        ("Breaking changes", [item for item in commits if item.breaking]),
        (
            "Features",
            [
                item
                for item in commits
                if not item.breaking and item.commit_type == "feat"
            ],
        ),
        (
            "Fixes",
            [
                item
                for item in commits
                if not item.breaking and item.commit_type in {"fix", "perf"}
            ],
        ),
        (
            "Maintenance",
            [
                item
                for item in commits
                if not item.breaking
                and item.commit_type not in {"feat", "fix", "perf"}
            ],
        ),
    ]

    for title, items in groups:
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for item in items:
            lines.append(
                f"- {item.description} (`{item.commit.sha[:7]}`, {item.commit_type})"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_outputs(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calculate the next automatic SemVer release from Git history."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    args = parser.parse_args()

    tags = list_stable_tags()
    head_tags = [(version, tag) for version, tag in tags if tag_points_at_head(tag)]

    if head_tags:
        version_tuple, tag = max(head_tags)
        lower_tags = [(v, t) for v, t in tags if v < version_tuple]
        previous_tag = max(lower_tags)[1] if lower_tags else None
        commits = load_commits(
            f"{previous_tag}..HEAD" if previous_tag else None
        )
        classified = [classify_commit(commit) for commit in commits]
        bump = highest_bump(classified) if classified else "patch"
        args.notes.write_text(
            notes_for(format_version(version_tuple), previous_tag, classified, bump),
            encoding="utf-8",
        )
        write_outputs(
            args.output,
            {
                "version": format_version(version_tuple),
                "tag": tag,
                "previous_tag": previous_tag or "",
                "bump": bump,
                "create_tag": "false",
                "publish_release": "true",
            },
        )
        return 0

    previous_version, previous_tag = tags[-1] if tags else ((0, 0, 0), None)
    commits = load_commits(f"{previous_tag}..HEAD" if previous_tag else None)
    if not commits:
        write_outputs(
            args.output,
            {
                "version": format_version(previous_version),
                "tag": previous_tag or "",
                "previous_tag": previous_tag or "",
                "bump": "patch",
                "create_tag": "false",
                "publish_release": "false",
            },
        )
        args.notes.write_text("", encoding="utf-8")
        return 0

    classified = [classify_commit(commit) for commit in commits]
    bump = highest_bump(classified)
    target = next_version(previous_version, bump)
    version = format_version(target)
    tag = f"v{version}"

    args.notes.write_text(
        notes_for(version, previous_tag, classified, bump),
        encoding="utf-8",
    )
    write_outputs(
        args.output,
        {
            "version": version,
            "tag": tag,
            "previous_tag": previous_tag or "",
            "bump": bump,
            "create_tag": "true",
            "publish_release": "true",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
