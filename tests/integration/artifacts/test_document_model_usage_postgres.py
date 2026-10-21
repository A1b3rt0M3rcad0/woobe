from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import func, select

from modules.metering.entrypoint import build_document_model_usage_consumer
from modules.metering.infra.database.models import InboxEventModel, UsageDailyProjectModel, UsageEventModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


EVENT = 'artifact.processing.model_usage.v1'


def envelope(project, *, call=None, usage=None, revision=1, input_tokens=None, output_tokens=None, cost=None):
    call, usage = call or uuid4(), usage or uuid4()
    payload = {'schema_version': '1', 'usage_event_id': str(usage), 'project_id': project,
        'environment': 'staging', 'job_id': str(uuid5(NAMESPACE_URL, 'job:' + str(call))), 'call_id': str(call),
        'provider': 'fixture-provider', 'model': 'fixture-model', 'provider_model_id': str(uuid5(NAMESPACE_URL, 'model:' + str(call))),
        'occurred_at': datetime(2026, 10, 20, tzinfo=UTC).isoformat(), 'observation_revision': revision,
        'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost_usd': cost,
        'cost_status': 'reported' if cost is not None else 'unknown', 'pricing_snapshot': None}
    identity = str(uuid5(NAMESPACE_URL, str(usage) + ':' + str(revision)))
    return {'id': identity, 'event_type': EVENT, 'idempotency_key': 'fixture:' + identity, 'payload': payload}


async def test_unknown_and_late_reported_usage_are_counted_once_without_fake_trace(engine, artifacts_database):
    project = artifacts_database['project_id']
    consume = build_document_model_usage_consumer(engine)
    first = envelope(project)
    await consume(first)
    await consume(first)
    second = envelope(project, call=first['payload']['call_id'], usage=first['payload']['usage_event_id'],
        revision=2, input_tokens=17, output_tokens=5, cost=0.002)
    await consume(second)
    await consume(second)
    await consume(first)
    async with ArtifactsUnitOfWork(engine) as uow:
        rows = (await uow.session.execute(select(UsageEventModel).where(UsageEventModel.project_id == project))).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.trace_id is None and row.agent_id is None and row.input_tokens == 17 and row.output_tokens == 5
        assert row.data['observation_revision'] == 2 and row.cost_status == 'reported'
        daily = await uow.session.scalar(select(UsageDailyProjectModel).where(UsageDailyProjectModel.project_id == project))
        assert daily.llm_calls == 1 and daily.input_tokens == 17 and daily.output_tokens == 5 and daily.cost_usd == 0.002
        assert await uow.session.scalar(select(func.count()).select_from(InboxEventModel).where(InboxEventModel.event_type == EVENT)) == 2
    conflict = {**second, 'id': str(uuid4()), 'idempotency_key': 'conflicting-observation',
        'payload': {**second['payload'], 'input_tokens': 99}}
    with pytest.raises(ValueError):
        await consume(conflict)
    regression = envelope(project, call=first['payload']['call_id'], usage=first['payload']['usage_event_id'], revision=3)
    with pytest.raises(ValueError):
        await consume(regression)


async def test_usage_observation_cannot_change_origin_or_accept_invalid_counts(engine, artifacts_database):
    consume = build_document_model_usage_consumer(engine)
    first = envelope(artifacts_database['project_id'])
    await consume(first)
    for change in ({'project_id': str(uuid4())}, {'call_id': str(uuid4())}, {'input_tokens': -1}):
        next_event = {**first, 'id': str(uuid4()), 'idempotency_key': uuid4().hex,
            'payload': {**first['payload'], 'observation_revision': 2, **change}}
        with pytest.raises(ValueError):
            await consume(next_event)
