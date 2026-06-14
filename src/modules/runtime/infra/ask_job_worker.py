"""Deprecated: AskJobWorker has moved to modules.agent.infra.workers.ask_job_worker.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.infra.ask_job_worker is deprecated. Use modules.agent.infra.workers.ask_job_worker instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.workers.ask_job_worker import AskJobWorker  # noqa: F401, E402
