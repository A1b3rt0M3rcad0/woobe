"""Idempotent usage observations for document operations without synthetic Runs."""
from datetime import datetime
import hashlib
import json
import math
from uuid import UUID

from sqlalchemy import func, select

from modules.metering.infra.database.models import UsageEventModel
from modules.metering.infra.messaging.daily_usage import _increment_daily


EVENT = 'artifact.processing.model_usage.v1'


async def handle_document_model_usage(event_type, payload, session=None, **kwargs):
    if session is None or event_type != EVENT:
        raise ValueError('Document model usage requires an owned metering session')
    project, source = UUID(payload['project_id']), UUID(payload['usage_event_id'])
    UUID(payload['job_id'])
    UUID(payload['call_id'])
    model_id = UUID(payload['provider_model_id'])
    revision = payload['observation_revision']
    occurred = datetime.fromisoformat(payload['occurred_at'])
    if (type(revision) is not int or revision < 1 or occurred.tzinfo is None
        or payload['environment'] not in {'draft', 'staging', 'production'}
        or payload['cost_status'] not in {'reported', 'estimated', 'unknown'}
        or not isinstance(payload['provider'], str) or not 1 <= len(payload['provider']) <= 64
        or not isinstance(payload['model'], str) or not 1 <= len(payload['model']) <= 255):
        raise ValueError('Invalid document model usage observation')
    for name in ('input_tokens', 'output_tokens'):
        value = payload.get(name)
        if value is not None and (type(value) is not int or not 0 <= value <= 9_223_372_036_854_775_807):
            raise ValueError('Invalid document model usage count')
    cost = payload.get('cost_usd')
    if cost is not None and (type(cost) not in {float, int} or not math.isfinite(cost) or cost < 0):
        raise ValueError('Invalid document model usage cost')
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(encoded) > 65536:
        raise ValueError('Document model usage observation exceeds its bound')
    fingerprint = hashlib.sha256(encoded).hexdigest()
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended('document-model-usage:' + str(source), 0))))
    row = await session.scalar(select(UsageEventModel).where(UsageEventModel.source_event_id == source).with_for_update())
    first = row is None
    before_input, before_output, before_cost = 0, 0, 0.0
    if row is not None:
        previous = row.data
        immutable = ('project_id', 'job_id', 'call_id', 'environment', 'provider', 'model', 'provider_model_id', 'occurred_at')
        if row.project_id != project or any(previous[name] != payload[name] for name in immutable):
            raise ValueError('Document usage origin cannot change')
        if revision < previous['observation_revision']:
            return
        if revision == previous['observation_revision']:
            if previous['_observation_fingerprint'] != fingerprint:
                raise ValueError('Document usage observation conflicts with its durable identity')
            return
        if any(previous.get(name) is not None and payload.get(name) is None for name in ('input_tokens', 'output_tokens', 'cost_usd')):
            raise ValueError('Known document usage cannot become unknown')
        before_input, before_output, before_cost = row.input_tokens or 0, row.output_tokens or 0, row.cost_usd or 0.0
    else:
        row = UsageEventModel(project_id=project, source_event_id=source, agent_id=None, trace_id=None,
            occurred_at=occurred, call_id=payload['call_id'], environment=payload['environment'],
            provider=payload['provider'], model=payload['model'], provider_model_id=model_id,
            event_type='llm_request', quantity=0, unit='token')
        session.add(row)
    row.input_tokens, row.output_tokens = payload.get('input_tokens'), payload.get('output_tokens')
    row.cost_usd, row.cost_status = cost, payload['cost_status']
    row.quantity = float((row.input_tokens or 0) + (row.output_tokens or 0))
    row.usage_complete = row.input_tokens is not None and row.output_tokens is not None
    row.pricing_snapshot = payload.get('pricing_snapshot')
    row.data = {**payload, '_observation_fingerprint': fingerprint}
    await _increment_daily(session, project_id=project, agent_id=None, day=occurred.date(), occurred_at=occurred,
        llm_calls=int(first), input_tokens=(row.input_tokens or 0)-before_input,
        output_tokens=(row.output_tokens or 0)-before_output, cost_usd=(cost or 0.0)-before_cost)
