from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.workers.runner import WorkerRunner


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def write_worker_health(path: str, runner: WorkerRunner) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runtime": "worker",
        "status": "ok",
        "observed_at": datetime.now(UTC).isoformat(),
        "workers": [
            {key: _serialize(value) for key, value in asdict(item).items()}
            for item in runner.get_health()
        ],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)


async def heartbeat_loop(
    *,
    path: str,
    runner: WorkerRunner,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        write_worker_health(path, runner)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    write_worker_health(path, runner)


def check_worker_health(path: str, max_age_seconds: float) -> int:
    target = Path(path)
    if not target.is_file():
        return 1
    age = time.time() - target.stat().st_mtime
    if age < 0 or age > max_age_seconds:
        return 1
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1
    workers = payload.get("workers")
    if not isinstance(workers, list) or not workers:
        return 1
    return 0 if all(item.get("is_running") for item in workers) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Woobe worker health probe")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("path")
    parser.add_argument("max_age_seconds", type=float)
    args = parser.parse_args()
    raise SystemExit(check_worker_health(args.path, args.max_age_seconds))


if __name__ == "__main__":
    main()
