"""Owned worker consumer for the standard Metering inbox."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modules.metering.infra.database.models import InboxEventModel
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.infra.messaging.document_model_usage import EVENT, handle_document_model_usage


def build_document_model_usage_consumer(engine):
    async def consume(envelope):
        if envelope['event_type'] != EVENT:
            raise ValueError('Unsupported document model usage event')
        identity = UUID(envelope['id'])
        async with MeteringUnitOfWork(engine) as uow:
            await uow.session.execute(insert(InboxEventModel).values(id=identity, message_id=str(identity),
                producer_module='artifacts', consumer_module='metering', outbox_origin_id=identity,
                aggregate_type='artifact-document-model-call', event_type=EVENT, event_version=1,
                routing_key=EVENT, payload=envelope['payload'], idempotency_key=envelope['idempotency_key'],
                status='received', attempts=0).on_conflict_do_nothing())
            event = await uow.session.scalar(select(InboxEventModel).where(InboxEventModel.id == identity).with_for_update())
            if event.payload != envelope['payload'] or event.idempotency_key != envelope['idempotency_key']:
                raise ValueError('Conflicting document usage inbox identity')
            if event.status == 'processed':
                return
            await handle_document_model_usage(EVENT, event.payload, session=uow.session)
            event.status, event.processed_at, event.attempts = 'processed', datetime.now(UTC), event.attempts + 1
    return consume
