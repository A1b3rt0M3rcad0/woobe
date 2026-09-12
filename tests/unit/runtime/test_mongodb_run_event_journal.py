from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError

from shared.contracts.run_event_journal import RunCheckpoint
from shared.infra.mongodb_run_event_journal import MongoDBRunEventJournal


@dataclass
class UpdateResult:
    matched_count: int


class FakeCheckpointCollection:
    def __init__(self) -> None:
        self.document: dict | None = None

    async def update_one(self, query, update, *, upsert: bool):
        assert upsert is False
        incoming = dict(update["$set"])
        if self.document is None:
            return UpdateResult(matched_count=0)
        if self.document["_id"] != query["_id"]:
            return UpdateResult(matched_count=0)
        if int(self.document.get("through_sequence") or 0) > int(
            incoming["through_sequence"]
        ):
            return UpdateResult(matched_count=0)
        self.document = incoming
        return UpdateResult(matched_count=1)

    async def insert_one(self, document):
        if self.document is not None:
            raise DuplicateKeyError("duplicate checkpoint")
        self.document = dict(document)


@pytest.mark.anyio
async def test_mongodb_checkpoint_never_regresses_on_late_writer() -> None:
    run_id = uuid4()
    collection = FakeCheckpointCollection()
    journal = object.__new__(MongoDBRunEventJournal)
    journal._checkpoints = collection

    await journal.upsert_checkpoint(
        RunCheckpoint(
            run_id=run_id,
            through_sequence=10,
            attempt=2,
            state={"next_step": "tool.completed"},
            updated_at="2026-09-10T00:00:10+00:00",
        )
    )
    await journal.upsert_checkpoint(
        RunCheckpoint(
            run_id=run_id,
            through_sequence=5,
            attempt=1,
            state={"next_step": "model.started"},
            updated_at="2026-09-10T00:00:05+00:00",
        )
    )

    assert collection.document is not None
    assert collection.document["through_sequence"] == 10
    assert collection.document["attempt"] == 2
    assert collection.document["state"] == {"next_step": "tool.completed"}
