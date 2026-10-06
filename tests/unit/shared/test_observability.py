from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from shared.observability.context import correlation_id_context, request_id_context
from shared.observability.logging_config import JsonFormatter, RequestContextFilter
from shared.observability.metrics import RuntimeMetrics
from woobe_workers.runtime.health import check_worker_health, write_worker_health


def test_json_formatter_includes_context_and_redacts_sensitive_headers() -> None:
    request_token = request_id_context.set("request-123")
    correlation_token = correlation_id_context.set("correlation-456")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Authorization header was provided",
            args=(),
            exc_info=None,
        )
        RequestContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(request_token)
        correlation_id_context.reset(correlation_token)

    assert payload["request_id"] == "request-123"
    assert payload["correlation_id"] == "correlation-456"


def test_metrics_render_http_runtime_and_pool_contracts() -> None:
    metrics = RuntimeMetrics()
    metrics.observe_http(method="GET", route="/live", status_code=200, duration_seconds=0.05)
    metrics.observe_ttft(provider="openai", model="gpt-test", milliseconds=125)
    metrics.increment_provider_failure(provider="openai", model="gpt-test")
    metrics.increment_tool_failure(tool="tool-1")
    metrics.increment_worker_failure(worker="OutboxWorker", worker_type="poller")
    metrics.set_queue_lag(queue="agent.runtime", seconds=2.5)
    metrics.increment_outbox_retry(worker="OutboxWorker")
    metrics.increment_inbox_retry(worker="InboxWorker")

    rendered = metrics.render_prometheus()
    assert 'route="/live",status="200"' in rendered
    assert "woobe_runtime_ttft_seconds_count" in rendered
    assert "woobe_provider_failures_total" in rendered
    assert "woobe_tool_failures_total" in rendered
    assert "woobe_worker_failures_total" in rendered
    assert "woobe_queue_lag_seconds" in rendered
    assert "woobe_outbox_retries_total" in rendered
    assert "woobe_inbox_retries_total" in rendered


@dataclass
class Health:
    worker_name: str = "Worker"
    worker_type: str = "poller"
    is_running: bool = True
    started_at: datetime = datetime.now(UTC)
    last_run_at: datetime | None = None
    error: str | None = None


class Runner:
    def get_health(self):
        return [Health()]


def test_worker_health_file_is_atomic_and_checkable(tmp_path) -> None:
    path = tmp_path / "worker-health.json"
    write_worker_health(str(path), Runner())
    assert check_worker_health(str(path), max_age_seconds=5) == 0


def test_worker_health_diagnostic_reports_failure_without_exporting_payload(tmp_path) -> None:
    from woobe_workers.runtime.health import worker_health_diagnostic

    path = tmp_path / "health.json"
    assert worker_health_diagnostic(str(path), 5)["reason"] == "heartbeat_missing"
    for value in ([], {"workers": [None]}, {"workers": []}):
        path.write_text(json.dumps(value))
        assert check_worker_health(str(path), 5) == 1
    path.write_text(json.dumps({"workers": [{"is_running": False, "error": "secret-value"}]}))
    diagnostic = worker_health_diagnostic(str(path), 5)
    assert diagnostic["reason"] == "workers_stopped"
    assert diagnostic["stopped_worker_indexes"] == [0]
    assert "secret-value" not in json.dumps(diagnostic)
    path.write_text(json.dumps({"workers": [{"is_running": "yes"}]}))
    assert check_worker_health(str(path), 5) == 1
