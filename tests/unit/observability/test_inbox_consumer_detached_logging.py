from __future__ import annotations

import inspect

from woobe_workers.consumers.observability.inbox_consumer import ObservabilityInboxConsumerWorker


def test_persist_and_ack_snapshots_log_fields_before_session_closes() -> None:
    source = inspect.getsource(ObservabilityInboxConsumerWorker._persist_and_ack)

    assert "event_type_snapshot" in source
    assert "message_id_snapshot" in source
    assert "idempotency_key_snapshot" in source

    session_pos = source.find("async with AsyncSession")
    event_snapshot_pos = source.find("event_type_snapshot")
    message_snapshot_pos = source.find("message_id_snapshot")
    idempotency_snapshot_pos = source.find("idempotency_key_snapshot")

    assert event_snapshot_pos < session_pos
    assert message_snapshot_pos < session_pos
    assert idempotency_snapshot_pos < session_pos


def test_persist_and_ack_logs_snapshots_not_detached_model_attributes() -> None:
    source = inspect.getsource(ObservabilityInboxConsumerWorker._persist_and_ack)

    assert "idempotency_key_snapshot," in source
    assert "event_type_snapshot," in source
    assert "message_id_snapshot," in source
    assert 'getattr(inbox_model, "event_type", "unknown"),' not in source
    assert 'getattr(inbox_model, "message_id", "unknown"),' not in source
    assert 'getattr(inbox_model, "idempotency_key", "unknown"),' not in source
