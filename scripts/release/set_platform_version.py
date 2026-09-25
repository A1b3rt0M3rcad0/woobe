"""Synchronize every static Woobe platform-version mirror from one target version."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def _replace_once(path: str, pattern: str, replacement: str) -> None:
    content = _read(path)
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one version match, found {count}")
    _write(path, updated)


def _replace_all(path: str, pattern: str, replacement: str) -> None:
    content = _read(path)
    updated, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count < 1:
        raise SystemExit(f"{path}: expected at least one version match")
    _write(path, updated)


def _set_package_json(path: str, version: str) -> None:
    data = json.loads(_read(path))
    data["version"] = version
    _write(path, json.dumps(data, indent=2) + "\n")


def _set_package_lock(path: str, version: str) -> None:
    data = json.loads(_read(path))
    data["version"] = version
    root = data.setdefault("packages", {}).setdefault("", {})
    root["version"] = version
    _write(path, json.dumps(data, indent=2) + "\n")


def _set_uv_lock(version: str) -> None:
    path = "uv.lock"
    pattern = r'(\[\[package\]\]\nname = "woobe"\nversion = ")[^"]+(")'
    _replace_once(path, pattern, rf"\g<1>{version}\2")


def synchronize(version: str) -> None:
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"invalid Semantic Version: {version}")

    _write("VERSION", version + "\n")

    for path in (
        "pyproject.toml",
        "packages/woobe-core/pyproject.toml",
        "packages/woobe-api/pyproject.toml",
        "packages/woobe-workers/pyproject.toml",
    ):
        _replace_once(path, r'^version = "[^"]+"$', f'version = "{version}"')

    for path in (
        "packages/woobe-api/pyproject.toml",
        "packages/woobe-workers/pyproject.toml",
    ):
        _replace_once(path, r'woobe-core==[^"]+', f"woobe-core=={version}")

    for path in (
        "packages/woobe-runtime-client/package.json",
        "packages/woobe-ui/package.json",
        "packages/woobe-frontend/package.json",
        "packages/woobe-embed/package.json",
    ):
        _set_package_json(path, version)

    for path in (
        "packages/woobe-frontend/package-lock.json",
        "packages/woobe-embed/package-lock.json",
    ):
        _set_package_lock(path, version)

    _set_uv_lock(version)

    _replace_once(
        "packages/woobe-api/src/main.py",
        r'version="[^"]+"',
        f'version="{version}"',
    )
    for path in (
        "packages/woobe-core/src/modules/agent/application/mcp_discovery.py",
        "packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py",
    ):
        _replace_all(
            path,
            r'("clientInfo": \{"name": "Woobe", "version": ")[^"]+("})',
            rf"\g<1>{version}\2",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Semantic version without the v prefix")
    args = parser.parse_args()
    synchronize(args.version)
    print(f"Woobe platform version synchronized to {args.version}")


if __name__ == "__main__":
    main()
