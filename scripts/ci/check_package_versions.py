"""Validate the canonical Woobe platform version across every release-bearing mirror."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _canonical_version() -> str:
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit("VERSION must not be empty")
    return value


def _toml_version(path: str) -> str:
    data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _json_version(path: str) -> str:
    return str(_json(path)["version"])


def _uv_project_version() -> str:
    content = (ROOT / "uv.lock").read_text(encoding="utf-8")
    match = re.search(
        r'\[\[package\]\]\nname = "woobe"\nversion = "([^"]+)"',
        content,
    )
    if not match:
        raise SystemExit("uv.lock does not contain the root woobe package")
    return match.group(1)


def _require_runtime_version(path: str, token: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    if token not in content:
        raise SystemExit(f"{path} does not expose canonical runtime version token {token!r}")


def main() -> None:
    expected = _canonical_version()
    versions = {
        "VERSION": expected,
        "woobe": _toml_version("pyproject.toml"),
        "woobe-core": _toml_version("packages/woobe-core/pyproject.toml"),
        "woobe-api": _toml_version("packages/woobe-api/pyproject.toml"),
        "woobe-workers": _toml_version("packages/woobe-workers/pyproject.toml"),
        "woobe-frontend": _json_version("packages/woobe-frontend/package.json"),
        "woobe-embed": _json_version("packages/woobe-embed/package.json"),
        "@woobe/runtime-client": _json_version("packages/woobe-runtime-client/package.json"),
        "@woobe/ui": _json_version("packages/woobe-ui/package.json"),
        "uv.lock": _uv_project_version(),
    }

    mismatches = {
        name: version
        for name, version in versions.items()
        if version != expected
    }
    if mismatches:
        details = ", ".join(f"{name}={version}" for name, version in sorted(mismatches.items()))
        raise SystemExit(f"release package versions must equal canonical VERSION {expected}: {details}")

    for package in ("woobe-api", "woobe-workers"):
        data = tomllib.loads(
            (ROOT / "packages" / package / "pyproject.toml").read_text(encoding="utf-8")
        )
        expected_dependency = f"woobe-core=={expected}"
        dependencies = set(data["project"].get("dependencies", []))
        if expected_dependency not in dependencies:
            raise SystemExit(
                f"{package} must depend on exact platform Core version {expected_dependency}"
            )

    for package in ("woobe-frontend", "woobe-embed"):
        lock = _json(f"packages/{package}/package-lock.json")
        root_package = lock.get("packages", {}).get("", {})
        for label, value in (
            ("lockfile version", lock.get("version")),
            ("root package version", root_package.get("version")),
        ):
            if str(value) != expected:
                raise SystemExit(
                    f"{package} {label} must equal platform version {expected}; got {value}"
                )

    _require_runtime_version(
        "packages/woobe-api/src/main.py",
        f'version="{expected}"',
    )
    runtime_token = f'"clientInfo": {{"name": "Woobe", "version": "{expected}"}}'
    _require_runtime_version(
        "packages/woobe-core/src/modules/agent/application/mcp_discovery.py",
        runtime_token,
    )
    _require_runtime_version(
        "packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py",
        runtime_token,
    )

    print(f"Woobe canonical platform version: {expected}")
    for name in sorted(versions):
        print(f"  {name}: {versions[name]}")


if __name__ == "__main__":
    main()
