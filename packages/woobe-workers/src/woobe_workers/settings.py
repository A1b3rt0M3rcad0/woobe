"""Configuration owned exclusively by the worker process host."""
from __future__ import annotations

from pydantic import Field

from shared.infra.config import Settings


class WorkerSettings(Settings):
    """Worker-host settings layered over product/runtime configuration."""

    service_role: str = "worker"
    artifact_processing_worker_slots: int = Field(default=1, ge=1, le=8)
    artifact_processing_lease_seconds: int = Field(default=30, ge=3, le=300)
    artifact_docling_memory_mib: int = Field(default=2048, ge=512, le=8192)
    artifact_docling_threads: int = Field(default=2, ge=1, le=8)
    network_worker_prefetch: int = Field(default=4, ge=1, le=100)
    network_worker_slots: int = Field(default=4, ge=1, le=100)
    worker_interval: float = Field(default=5.0, gt=0)
    worker_health_file: str = "/tmp/woobe/worker-health.json"
    worker_heartbeat_interval_seconds: float = Field(default=10.0, gt=0, le=60)
    worker_health_max_age_seconds: float = Field(default=45.0, gt=5, le=300)
    run_event_batch_size: int = Field(default=250, ge=1, le=5000)
    run_event_flush_interval_ms: int = Field(default=200, ge=10, le=5000)
    run_event_claim_idle_seconds: int = Field(default=30, ge=1, le=3600)
    run_event_redis_consumer_group: str = "woobe-run-journal"
