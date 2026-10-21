"""Fence restored Workspaces listed by the authoritative post-backup purge ledger."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/woobe-core/src"))

from modules.artifacts.infra.database.lifecycle import ArtifactLifecycleRepository  # noqa: E402


async def _reconcile(database_url: str, workspace_ids: tuple[str, ...]) -> int:
    engine = create_async_engine(database_url)
    try:
        return await ArtifactLifecycleRepository(engine).reconcile_restore_tombstones(workspace_ids)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tombstones", type=Path, help="JSON from the current authoritative lifecycle ledger")
    args = parser.parse_args()
    database_url = os.environ.get("WOOBE_DATABASE_URL")
    if not database_url:
        parser.error("WOOBE_DATABASE_URL must point to the isolated restored PostgreSQL database")
    raw = args.tombstones.read_bytes()
    if len(raw) > 1_048_576:
        parser.error("tombstone input exceeds 1 MiB")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        parser.error(f"invalid tombstone JSON: {error}")
    checkpoint = document.get("source_checkpoint") if isinstance(document, dict) else None
    values = document.get("workspace_ids") if isinstance(document, dict) else None
    if (not isinstance(checkpoint, str) or not checkpoint.strip() or len(checkpoint) > 255
            or not isinstance(values, list) or not 1 <= len(values) <= 1000
            or any(not isinstance(value, str) for value in values)):
        parser.error("expected source_checkpoint and 1–1000 workspace_ids")
    count = asyncio.run(_reconcile(database_url, tuple(values)))
    print(json.dumps({
        "source_checkpoint": checkpoint,
        "workspace_count": len(set(values)),
        "newly_fenced": count,
        "next_action": "keep the restored API offline until the lifecycle worker completes purge",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
