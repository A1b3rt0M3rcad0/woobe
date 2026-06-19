"""Persistence-aware runtime finalization adapters."""

from modules.agent.infra.runtime.instrumented_execution_finalizer import (
    finalize_instrumented_execution,
)

__all__ = ["finalize_instrumented_execution"]
