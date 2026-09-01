from __future__ import annotations

import math
import threading
from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**labels: str) -> str:
    if not labels:
        return ""
    rendered = ",".join(
        f'{key}="{_escape_label(value)}"' for key, value in sorted(labels.items())
    )
    return "{" + rendered + "}"


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self._http_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._http_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._provider_failures: dict[tuple[str, str], int] = defaultdict(int)
        self._tool_failures: dict[str, int] = defaultdict(int)
        self._ttft_count: dict[tuple[str, str], int] = defaultdict(int)
        self._ttft_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._worker_failures: dict[tuple[str, str], int] = defaultdict(int)
        self._queue_lag_seconds: dict[str, float] = {}
        self._outbox_retries: dict[str, int] = defaultdict(int)
        self._inbox_retries: dict[str, int] = defaultdict(int)

    def observe_http(self, *, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        route_key = route if route.startswith("/") else "unknown"
        with self._lock:
            self._http_requests[(method, route_key, str(status_code))] += 1
            self._http_duration_count[(method, route_key)] += 1
            self._http_duration_sum[(method, route_key)] += duration_seconds

    def increment_provider_failure(self, *, provider: str, model: str) -> None:
        with self._lock:
            self._provider_failures[(provider or "unknown", model or "unknown")] += 1

    def increment_tool_failure(self, *, tool: str) -> None:
        with self._lock:
            self._tool_failures[tool or "unknown"] += 1

    def observe_ttft(self, *, provider: str, model: str, milliseconds: int) -> None:
        key = (provider or "unknown", model or "unknown")
        with self._lock:
            self._ttft_count[key] += 1
            self._ttft_sum[key] += milliseconds / 1000

    def increment_worker_failure(self, *, worker: str, worker_type: str) -> None:
        with self._lock:
            self._worker_failures[(worker, worker_type)] += 1

    def set_queue_lag(self, *, queue: str, seconds: float) -> None:
        with self._lock:
            self._queue_lag_seconds[queue] = max(seconds, 0.0)

    def increment_outbox_retry(self, *, worker: str) -> None:
        with self._lock:
            self._outbox_retries[worker] += 1

    def increment_inbox_retry(self, *, worker: str) -> None:
        with self._lock:
            self._inbox_retries[worker] += 1

    @staticmethod
    def _db_pool_samples(engine: Any | None) -> Iterable[str]:
        if engine is None:
            return []
        try:
            pool = engine.sync_engine.pool
            return [
                f"woobe_db_pool_size {float(pool.size())}",
                f"woobe_db_pool_checked_out {float(pool.checkedout())}",
                f"woobe_db_pool_overflow {float(pool.overflow())}",
            ]
        except (AttributeError, NotImplementedError, TypeError):
            return []

    def render_prometheus(self, *, engine: Any | None = None) -> str:
        with self._lock:
            http_requests = dict(self._http_requests)
            http_duration_count = dict(self._http_duration_count)
            http_duration_sum = dict(self._http_duration_sum)
            provider_failures = dict(self._provider_failures)
            tool_failures = dict(self._tool_failures)
            ttft_count = dict(self._ttft_count)
            ttft_sum = dict(self._ttft_sum)
            worker_failures = dict(self._worker_failures)
            queue_lag = dict(self._queue_lag_seconds)
            outbox_retries = dict(self._outbox_retries)
            inbox_retries = dict(self._inbox_retries)

        lines = [
            "# HELP woobe_http_requests_total HTTP requests by route and status.",
            "# TYPE woobe_http_requests_total counter",
        ]
        for (method, route, status), value in sorted(http_requests.items()):
            lines.append("woobe_http_requests_total" + _labels(method=method, route=route, status=status) + f" {value}")
        lines.extend([
            "# HELP woobe_http_request_duration_seconds HTTP request latency.",
            "# TYPE woobe_http_request_duration_seconds summary",
        ])
        for (method, route), value in sorted(http_duration_count.items()):
            label_set = _labels(method=method, route=route)
            lines.append(f"woobe_http_request_duration_seconds_count{label_set} {value}")
            lines.append(f"woobe_http_request_duration_seconds_sum{label_set} {http_duration_sum[(method, route)]:.9f}")
        lines.extend([
            "# HELP woobe_provider_failures_total Provider invocation failures.",
            "# TYPE woobe_provider_failures_total counter",
        ])
        for (provider, model), value in sorted(provider_failures.items()):
            lines.append("woobe_provider_failures_total" + _labels(provider=provider, model=model) + f" {value}")
        lines.extend([
            "# HELP woobe_tool_failures_total Tool execution failures.",
            "# TYPE woobe_tool_failures_total counter",
        ])
        for tool, value in sorted(tool_failures.items()):
            lines.append("woobe_tool_failures_total" + _labels(tool=tool) + f" {value}")
        lines.extend([
            "# HELP woobe_runtime_ttft_seconds Time to first streamed token.",
            "# TYPE woobe_runtime_ttft_seconds summary",
        ])
        for (provider, model), value in sorted(ttft_count.items()):
            label_set = _labels(provider=provider, model=model)
            lines.append(f"woobe_runtime_ttft_seconds_count{label_set} {value}")
            lines.append(f"woobe_runtime_ttft_seconds_sum{label_set} {ttft_sum[(provider, model)]:.9f}")
        lines.extend([
            "# HELP woobe_worker_failures_total Worker loop failures.",
            "# TYPE woobe_worker_failures_total counter",
        ])
        for (worker, worker_type), value in sorted(worker_failures.items()):
            lines.append("woobe_worker_failures_total" + _labels(worker=worker, worker_type=worker_type) + f" {value}")
        lines.extend([
            "# HELP woobe_queue_lag_seconds Oldest observed queue message age.",
            "# TYPE woobe_queue_lag_seconds gauge",
        ])
        for queue, value in sorted(queue_lag.items()):
            if math.isfinite(value):
                lines.append("woobe_queue_lag_seconds" + _labels(queue=queue) + f" {value}")
        lines.extend([
            "# HELP woobe_outbox_retries_total Outbox publish retries.",
            "# TYPE woobe_outbox_retries_total counter",
        ])
        for worker, value in sorted(outbox_retries.items()):
            lines.append("woobe_outbox_retries_total" + _labels(worker=worker) + f" {value}")
        lines.extend([
            "# HELP woobe_inbox_retries_total Inbox processing retries.",
            "# TYPE woobe_inbox_retries_total counter",
        ])
        for worker, value in sorted(inbox_retries.items()):
            lines.append("woobe_inbox_retries_total" + _labels(worker=worker) + f" {value}")
        lines.extend([
            "# HELP woobe_db_pool_size Configured SQLAlchemy pool size.",
            "# TYPE woobe_db_pool_size gauge",
            "# HELP woobe_db_pool_checked_out Checked-out DB connections.",
            "# TYPE woobe_db_pool_checked_out gauge",
            "# HELP woobe_db_pool_overflow Current DB overflow connections.",
            "# TYPE woobe_db_pool_overflow gauge",
        ])
        lines.extend(self._db_pool_samples(engine))
        return "\n".join(lines) + "\n"


runtime_metrics = RuntimeMetrics()
