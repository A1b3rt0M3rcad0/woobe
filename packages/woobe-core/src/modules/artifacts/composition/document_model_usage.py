"""Bounded outbox delivery; receiver owns a separate short inbox transaction."""
from sqlalchemy import select

from modules.artifacts.infra.database.models import ArtifactProcessingOutboxModel as Outbox
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.composition.document_model_operations import document_model_usage_consumer


EVENT = 'artifact.processing.model_usage.v1'


def model_usage_delivery(engine, deliver_jobs):
    consume = document_model_usage_consumer(engine)

    async def deliver(limit):
        count = await deliver_jobs(limit)
        async with ArtifactsUnitOfWork(engine) as uow:
            rows = (await uow.session.execute(select(Outbox).where(Outbox.status == 'pending',
                Outbox.event_type == EVENT).order_by(Outbox.created_at, Outbox.id).limit(min(10, limit)))).scalars()
            envelopes = [{'id': str(row.id), 'event_type': row.event_type, 'payload': row.payload,
                'idempotency_key': row.idempotency_key} for row in rows]
        for envelope in envelopes:
            await consume(envelope)
            async with ArtifactsUnitOfWork(engine) as uow:
                from datetime import UTC, datetime
                from uuid import UUID
                row = await uow.session.scalar(select(Outbox).where(Outbox.id == UUID(envelope['id'])).with_for_update())
                if row.status == 'pending':
                    row.status, row.published_at, row.attempts = 'published', datetime.now(UTC), row.attempts + 1
                    count += 1
        return count
    return deliver
