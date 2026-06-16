"""Replay inbox or outbox events by status/range.

Usage:
    python -m scripts.messaging.replay --module metering --type inbox --status failed
    python -m scripts.messaging.replay --module observability --type outbox --dead
    python -m scripts.messaging.replay --agent --type inbox --ids <uuid1> <uuid2>
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

logger = logging.getLogger(__name__)

MODULE_INBOX_MODELS: dict[str, Any] = {}
MODULE_OUTBOX_MODELS: dict[str, Any] = {}

try:
    from modules.agent.infra.database.models import AgentInboxEventModel, AgentOutboxEventModel
    MODULE_INBOX_MODELS["agent"] = AgentInboxEventModel
    MODULE_OUTBOX_MODELS["agent"] = AgentOutboxEventModel
except ImportError:
    pass

try:
    from modules.metering.infra.database.models import InboxEventModel as MeteringInbox
    from modules.metering.infra.database.models import OutboxEventModel as MeteringOutbox
    MODULE_INBOX_MODELS["metering"] = MeteringInbox
    MODULE_OUTBOX_MODELS["metering"] = MeteringOutbox
except ImportError:
    pass

try:
    from modules.observability.infra.database.models import InboxEventModel as ObservabilityInbox
    from modules.observability.infra.database.models import OutboxEventModel as ObservabilityOutbox
    MODULE_INBOX_MODELS["observability"] = ObservabilityInbox
    MODULE_OUTBOX_MODELS["observability"] = ObservabilityOutbox
except ImportError:
    pass


async def replay_events(
    engine_url: str,
    module: str,
    box_type: str,
    status: str | None = None,
    dead: bool = False,
    ids: list[str] | None = None,
) -> int:
    engine = create_async_engine(engine_url)

    if box_type == "inbox":
        model = MODULE_INBOX_MODELS.get(module)
    else:
        model = MODULE_OUTBOX_MODELS.get(module)

    if model is None:
        logger.error("Unknown module/box type: %s/%s", module, box_type)
        return 1

    async with AsyncSession(engine) as session:
        stmt = select(model)

        if dead:
            stmt = stmt.where(model.status == "dead")
        elif status:
            stmt = stmt.where(model.status == status)

        if ids:
            uuid_ids = [UUID(id_str) for id_str in ids]
            stmt = stmt.where(model.id.in_(uuid_ids))

        result = await session.execute(stmt)
        events = list(result.scalars().all())

        if not events:
            logger.info("No events found to replay")
            return 0

        new_status = "pending" if box_type == "outbox" else "received"
        update_stmt = (
            update(model)
            .where(model.id.in_([e.id for e in events]))
            .values(
                status=new_status,
                attempts=0,
                error=None,
                locked_at=None,
                locked_by=None,
                available_at=datetime.now(timezone.utc),
                processed_at=None,
            )
        )
        await session.execute(update_stmt)
        await session.commit()

    logger.info("Requeued %d %s %s events", len(events), module, box_type)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay inbox/outbox events")
    parser.add_argument("--engine-url", default="postgresql+asyncpg://localhost:5432/projectrai")
    parser.add_argument("--module", required=True, choices=["agent", "metering", "observability"])
    parser.add_argument("--type", dest="box_type", required=True, choices=["inbox", "outbox"])
    parser.add_argument("--status", help="Filter by status (failed, retryable, etc.)")
    parser.add_argument("--dead", action="store_true", help="Replay dead events")
    parser.add_argument("--ids", nargs="+", help="Specific event IDs")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    exit_code = asyncio.run(replay_events(
        engine_url=args.engine_url,
        module=args.module,
        box_type=args.box_type,
        status=args.status,
        dead=args.dead,
        ids=args.ids,
    ))
    exit(exit_code)


if __name__ == "__main__":
    main()
