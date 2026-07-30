from __future__ import annotations

import re
from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_SOURCE = _REPOSITORY_ROOT / "web" / "src"
_UUID_HELPER = _FRONTEND_SOURCE / "lib" / "uuid.ts"
_DIRECT_RANDOM_UUID = re.compile(
    r"\b(?:(?:globalThis|window)\.)?crypto(?:\?\.|\.)randomUUID(?:\?\.)?\s*\("
)


def test_frontend_uses_the_browser_safe_uuid_helper() -> None:
    offenders: list[str] = []

    for path in sorted(_FRONTEND_SOURCE.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if path == _UUID_HELPER or ".test." in path.name or ".spec." in path.name:
            continue

        source = path.read_text(encoding="utf-8")
        if _DIRECT_RANDOM_UUID.search(source):
            offenders.append(str(path.relative_to(_REPOSITORY_ROOT)))

    assert not offenders, (
        "Frontend modules must use web/src/lib/uuid.ts instead of calling "
        f"crypto.randomUUID directly. Offenders: {', '.join(offenders)}"
    )
