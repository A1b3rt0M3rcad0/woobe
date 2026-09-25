"""Validate one platform version across release-bearing Woobe packages."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _toml_version(path: str) -> str:
    data = tomllib.loads((ROOT / path).read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _json_version(path: str) -> str:
    return str(_json(path)["version"])


def main() -> None:
    expected = _toml_version("pyproject.toml")
    versions = {
        "woobe": expected,
        "woobe-core": _toml_version("packages/woobe-core/pyproject.toml"),
        "woobe-api": _toml_version("packages/woobe-api/pyproject.toml"),
        "woobe-workers": _toml_version("packages/woobe-workers/pyproject.toml"),
        "woobe-frontend": _json_version("packages/woobe-frontend/package.json"),
        "woobe-embed": _json_version("packages/woobe-embed/package.json"),
        "@woobe/runtime-client": _json_version("packages/woobe-runtime-client/package.json"),
        "@woobe/ui": _json_version("packages/woobe-ui/package.json"),
    }

    mismatches = {
        name: version
        for name, version in versions.items()
        if version != expected
    }
    if mismatches:
        details = ", ".join(f"{name}={version}" for name, version in sorted(mismatches.items()))
        raise SystemExit(f"release package versions must equal {expected}: {details}")

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

    print(f"Woobe package version contract: {expected}")
    for name in sorted(versions):
        print(f"  {name}: {versions[name]}")


if __name__ == "__main__":
    main()
