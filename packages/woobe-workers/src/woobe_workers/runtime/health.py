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
    from woobe_workers.runtime.runner import WorkerRunner


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


def worker_health_diagnostic(path: str, max_age_seconds: float) -> dict[str, Any]:
    """Report probe failure without exporting arbitrary file contents or secrets."""
    target = Path(path)
    try:
        age = time.time() - target.stat().st_mtime
        if age < 0 or age > max_age_seconds:
            return {"healthy": False, "reason": "heartbeat_age", "age_seconds": age}
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"healthy": False, "reason": "heartbeat_missing"}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"healthy": False, "reason": "heartbeat_unreadable"}
    if not isinstance(payload, dict):
        return {"healthy": False, "reason": "invalid_payload"}
    workers = payload.get("workers")
    if not isinstance(workers, list) or not workers or any(not isinstance(item, dict) for item in workers):
        return {"healthy": False, "reason": "invalid_workers"}
    stopped = [index for index, item in enumerate(workers) if item.get("is_running") is not True]
    return {"healthy": not stopped, "reason": "workers_stopped" if stopped else "ok", "stopped_worker_indexes": stopped, "worker_count": len(workers)}


def check_worker_health(path: str, max_age_seconds: float) -> int:
    return 0 if worker_health_diagnostic(path, max_age_seconds)["healthy"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Woobe worker health probe")
    parser.add_argument("command", choices=["check", "diagnose"])
    parser.add_argument("path")
    parser.add_argument("max_age_seconds", type=float)
    args = parser.parse_args()
    if args.command == "diagnose":
        print(json.dumps(worker_health_diagnostic(args.path, args.max_age_seconds)))
    raise SystemExit(check_worker_health(args.path, args.max_age_seconds))


if __name__ == "__main__":
    main()
