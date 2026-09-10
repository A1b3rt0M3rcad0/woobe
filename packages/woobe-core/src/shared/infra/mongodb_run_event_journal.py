from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, ReplaceOne
from pymongo.errors import DuplicateKeyError

from shared.contracts.run_event_journal import (
    DurableRunEvent,
    RunCheckpoint,
    RunEventJournalPort,
    RunJournalState,
)
from shared.runtime.event_schema import CHECKPOINT_EVENT_TYPE, TERMINAL_EVENT_TYPES


class MongoDBRunEventJournal(RunEventJournalPort):
    """Append-only MongoDB journal. Redis delivery is at-least-once; writes are idempotent."""

    def __init__(self, client: AsyncMongoClient, database: str) -> None:
        self._client = client
        self._db = client[database]
        self._events = self._db["run_events"]
        self._states = self._db["run_journal_state"]
        self._checkpoints = self._db["run_checkpoints"]

    async def ensure_indexes(self) -> None:
        await self._events.create_index(
            [("run_id", ASCENDING), ("sequence", ASCENDING)],
            unique=True,
            name="uq_run_sequence",
        )
        await self._events.create_index(
            [("project_id", ASCENDING), ("occurred_at", DESCENDING)],
            name="ix_project_occurred",
        )
        await self._events.create_index(
            [("trace_id", ASCENDING), ("sequence", ASCENDING)],
            name="ix_trace_sequence",
            sparse=True,
        )
        await self._events.create_index(
            [("event_type", ASCENDING), ("occurred_at", DESCENDING)],
            name="ix_type_occurred",
        )

    @staticmethod
    def _document(event: DurableRunEvent) -> dict[str, Any]:
        metadata = dict(event.metadata)
        return {
            "_id": f"{event.run_id}:{event.sequence}",
            "schema_version": event.schema_version,
            "storage_version": event.storage_version,
            "event_id": event.event_id,
            "run_id": str(event.run_id),
            "run_kind": event.run_kind,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "project_id": metadata.get("project_id"),
            "trace_id": metadata.get("trace_id"),
            "agent_id": metadata.get("agent_id"),
            "network_id": metadata.get("network_id"),
            "session_id": metadata.get("session_id"),
            "network_session_id": metadata.get("network_session_id"),
            "network_execution_id": metadata.get("network_execution_id"),
            "invocation_id": metadata.get("invocation_id"),
            "parent_invocation_id": metadata.get("parent_invocation_id"),
            "attempt": int(metadata.get("attempt") or 1),
            "visibility": metadata.get("visibility") or "internal",
            "metadata": metadata,
            "payload": dict(event.payload),
        }

    @staticmethod
    def _event(document: dict[str, Any]) -> DurableRunEvent:
        return DurableRunEvent(
            run_id=UUID(str(document["run_id"])),
            run_kind=str(document["run_kind"]),
            sequence=int(document["sequence"]),
            event_id=str(document["event_id"]),
            event_type=str(document["event_type"]),
            occurred_at=str(document["occurred_at"]),
            schema_version=int(document.get("schema_version") or 1),
            storage_version=str(document.get("storage_version") or "event_journal_v1"),
            metadata=dict(document.get("metadata") or {}),
            payload=dict(document.get("payload") or {}),
        )

    async def write_batch(self, events: Sequence[DurableRunEvent]) -> None:
        if not events:
            return
        operations = [
            ReplaceOne(
                {"_id": f"{event.run_id}:{event.sequence}"},
                self._document(event),
                upsert=True,
            )
            for event in events
        ]
        await self._events.bulk_write(operations, ordered=False)
        for event in events:
            if event.event_type != CHECKPOINT_EVENT_TYPE:
                continue
            raw_state = event.payload.get("state")
            if not isinstance(raw_state, dict):
                continue
            await self.upsert_checkpoint(
                RunCheckpoint(
                    run_id=event.run_id,
                    through_sequence=event.sequence,
                    attempt=int(
                        event.payload.get("attempt")
                        or event.metadata.get("attempt")
                        or 1
                    ),
                    state=dict(raw_state),
                    updated_at=event.occurred_at,
                )
            )

    async def list_events(
        self,
        run_id: UUID,
        *,
        after_sequence: int = 0,
        through_sequence: int | None = None,
        limit: int = 5000,
    ) -> list[DurableRunEvent]:
        query: dict[str, Any] = {
            "run_id": str(run_id),
            "sequence": {"$gt": int(after_sequence)},
        }
        if through_sequence is not None:
            query["sequence"]["$lte"] = int(through_sequence)
        cursor = (
            self._events.find(query)
            .sort("sequence", ASCENDING)
            .limit(max(1, int(limit)))
        )
        return [self._event(document) async for document in cursor]

    async def get_state(self, run_id: UUID) -> RunJournalState | None:
        document = await self._states.find_one({"_id": str(run_id)})
        if document is None:
            return None
        return RunJournalState(
            run_id=run_id,
            run_kind=str(document.get("run_kind") or "agent"),
            storage_version=str(document.get("storage_version") or "event_journal_v1"),
            durable_sequence=int(document.get("durable_sequence") or 0),
            checkpoint_sequence=int(document.get("checkpoint_sequence") or 0),
            terminal_sequence=(
                int(document["terminal_sequence"])
                if document.get("terminal_sequence") is not None
                else None
            ),
            terminal_status=(
                str(document["terminal_status"])
                if document.get("terminal_status") is not None
                else None
            ),
            updated_at=(str(document["updated_at"]) if document.get("updated_at") else None),
        )

    async def advance_durable_sequence(
        self,
        run_id: UUID,
        *,
        run_kind: str,
        storage_version: str,
    ) -> RunJournalState:
        previous = await self.get_state(run_id)
        durable = previous.durable_sequence if previous is not None else 0
        checkpoint_sequence = previous.checkpoint_sequence if previous is not None else 0
        terminal_sequence = previous.terminal_sequence if previous is not None else None
        terminal_status = previous.terminal_status if previous is not None else None

        cursor = self._events.find(
            {"run_id": str(run_id), "sequence": {"$gt": durable}},
            {"sequence": 1, "event_type": 1},
        ).sort("sequence", ASCENDING)
        expected = durable + 1
        async for document in cursor:
            sequence = int(document["sequence"])
            if sequence != expected:
                break
            durable = sequence
            event_type = str(document["event_type"])
            if event_type == CHECKPOINT_EVENT_TYPE:
                checkpoint_sequence = sequence
            status = TERMINAL_EVENT_TYPES.get(event_type)
            if status is not None:
                terminal_sequence = sequence
                terminal_status = status
            expected += 1

        now = datetime.now(timezone.utc).isoformat()
        await self._states.update_one(
            {"_id": str(run_id)},
            {
                "$set": {
                    "run_kind": run_kind,
                    "storage_version": storage_version,
                    "durable_sequence": durable,
                    "checkpoint_sequence": checkpoint_sequence,
                    "terminal_sequence": terminal_sequence,
                    "terminal_status": terminal_status,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        return RunJournalState(
            run_id=run_id,
            run_kind=run_kind,
            storage_version=storage_version,
            durable_sequence=durable,
            checkpoint_sequence=checkpoint_sequence,
            terminal_sequence=terminal_sequence,
            terminal_status=terminal_status,
            updated_at=now,
        )

    async def upsert_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        checkpoint_id = str(checkpoint.run_id)
        document = {
            "_id": checkpoint_id,
            "run_id": checkpoint_id,
            "through_sequence": checkpoint.through_sequence,
            "attempt": checkpoint.attempt,
            "state": dict(checkpoint.state),
            "updated_at": checkpoint.updated_at,
        }
        result = await self._checkpoints.update_one(
            {
                "_id": checkpoint_id,
                "$or": [
                    {"through_sequence": {"$lte": checkpoint.through_sequence}},
                    {"through_sequence": {"$exists": False}},
                ],
            },
            {"$set": document},
            upsert=False,
        )
        if result.matched_count:
            return

        try:
            await self._checkpoints.insert_one(document)
        except DuplicateKeyError:
            # Another writer either created the same checkpoint or already moved
            # this Run to a newer sequence. Never let a late checkpoint regress it.
            return

    async def latest_checkpoint(self, run_id: UUID) -> RunCheckpoint | None:
        document = await self._checkpoints.find_one({"_id": str(run_id)})
        if document is None:
            return None
        return RunCheckpoint(
            run_id=run_id,
            through_sequence=int(document.get("through_sequence") or 0),
            attempt=int(document.get("attempt") or 1),
            state=dict(document.get("state") or {}),
            updated_at=str(document.get("updated_at") or ""),
        )

    async def close(self) -> None:
        await self._client.close()
