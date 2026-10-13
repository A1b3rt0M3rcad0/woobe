#!/usr/bin/env python3
"""Build a deliberately polluted context with the real ignore rules; verify exported content."""

import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ignore", type=Path, default=Path(".dockerignore"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="woobe-context-proof-") as directory:
        root = Path(directory)
        context = root / "context"
        context.mkdir()
        (context / ".dockerignore").write_bytes(args.ignore.read_bytes())
        for package in (
            "woobe-frontend",
            "woobe-embed",
            "woobe-runtime-client",
            "nested/deep",
        ):
            folder = context / "packages" / package
            (folder / "node_modules/host-only").mkdir(parents=True)
            (folder / "node_modules/host-only/windows.dll").write_bytes(
                b"WINDOWS_HOST_ONLY"
            )
            (folder / "tsconfig.tsbuildinfo").write_text("INVALID_HOST_BUILD_CACHE")
            (folder / "source.ts").write_text("export const source = true")
        (context / "Dockerfile").write_text("FROM scratch\nCOPY packages /packages\n")
        result = subprocess.run(
            [
                "docker",
                "buildx",
                "build",
                "--progress=plain",
                "--output",
                f"type=local,dest={root / 'output'}",
                str(context),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise SystemExit(result.stderr)
        exported = root / "output/packages"
        assert len(list(exported.rglob("source.ts"))) == 4, (
            "Source was accidentally excluded"
        )
        assert not list(exported.rglob("node_modules")), (
            "Host dependencies entered build context"
        )
        assert not list(exported.rglob("*.tsbuildinfo")), (
            "Host compiler cache entered build context"
        )
        print(
            "PASS: four nested packages preserve source and exclude poisoned host dependencies/caches"
        )


if __name__ == "__main__":
    main()
