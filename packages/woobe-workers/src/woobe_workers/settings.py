"""Configuration owned exclusively by the worker process host."""
from __future__ import annotations

from pydantic import Field

from shared.infra.config import Settings


class WorkerSettings(Settings):
    """Worker-host settings layered over product/runtime configuration."""

    service_role: str = "worker"
    network_worker_prefetch: int = Field(default=4, ge=1, le=100)
    network_worker_slots: int = Field(default=4, ge=1, le=100)
    worker_interval: float = Field(default=5.0, gt=0)
    worker_health_file: str = "/tmp/woobe/worker-health.json"
    worker_heartbeat_interval_seconds: float = Field(default=10.0, gt=0, le=60)
    worker_health_max_age_seconds: float = Field(default=45.0, gt=5, le=300)
