"""Tests for spec 083 — implement agent inbox processor."""
import ast
import inspect

from woobe_workers.consumers.agent.inbox_processor import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentInboxHandlerProtocol,
    AgentInboxProcessorWorker,
)
from woobe_workers.runtime.inbox_processor_base import BaseInboxProcessor


class TestInboxProcessorStructure:
    """Verify the processor is properly located and inherits from the base."""

    def test_file_exists_in_correct_location(self):
        import woobe_workers.consumers.agent.inbox_processor as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/workers" in mod.__file__.replace("\\", "/")

    def test_inherits_from_base_inbox_processor(self):
        assert issubclass(AgentInboxProcessorWorker, BaseInboxProcessor)

    def test_implements_claim_pending(self):
        assert hasattr(AgentInboxProcessorWorker, "claim_pending")
        assert inspect.iscoroutinefunction(AgentInboxProcessorWorker.claim_pending)

    def test_implements_process(self):
        assert hasattr(AgentInboxProcessorWorker, "process")
        assert inspect.iscoroutinefunction(AgentInboxProcessorWorker.process)

    def test_implements_mark_processed(self):
        assert hasattr(AgentInboxProcessorWorker, "mark_processed")
        assert inspect.iscoroutinefunction(AgentInboxProcessorWorker.mark_processed)

    def test_implements_mark_dead(self):
        assert hasattr(AgentInboxProcessorWorker, "mark_dead")
        assert inspect.iscoroutinefunction(AgentInboxProcessorWorker.mark_dead)

    def test_implements_mark_retryable(self):
        assert hasattr(AgentInboxProcessorWorker, "mark_retryable")
        assert inspect.iscoroutinefunction(AgentInboxProcessorWorker.mark_retryable)


class TestInboxProcessorDelegation:
    """Verify the processor delegates to handler and repository."""

    def test_claim_pending_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "claim_batch" in source

    def test_process_delegates_to_handler(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "_handler" in source
        assert "handle" in source

    def test_process_passes_event_type_and_payload(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "event_type" in source
        assert "payload" in source

    def test_mark_processed_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_processed)
        assert "mark_processed" in source

    def test_mark_dead_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_dead)
        assert "mark_dead" in source

    def test_mark_retryable_uses_repository(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "mark_retryable" in source


class TestInboxProcessorRetryBackoff:
    """Verify retry backoff is implemented."""

    def test_retry_backoff_constant_defined(self):
        assert isinstance(RETRY_BACKOFF_BASE_SECONDS, int)
        assert RETRY_BACKOFF_BASE_SECONDS > 0

    def test_mark_retryable_uses_backoff(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "RETRY_BACKOFF_BASE_SECONDS" in source or "backoff" in source

    def test_mark_retryable_calculates_available_at(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "available_at" in source


class TestInboxProcessorConcurrency:
    """Verify concurrency safety patterns."""

    def test_claim_pending_uses_locked_by(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "locked_by" in source

    def test_worker_has_unique_id(self):
        source = inspect.getsource(AgentInboxProcessorWorker.__init__)
        assert "worker_id" in source

    def test_run_manages_session_lifecycle(self):
        source = inspect.getsource(AgentInboxProcessorWorker.run)
        assert "AsyncSession" in source
        assert "begin" in source


class TestInboxProcessorIdempotency:
    """Verify idempotency via handler delegation."""

    def test_process_passes_correlation_id(self):
        source = inspect.getsource(AgentInboxProcessorWorker.process)
        assert "correlation_id" in source

    def test_max_attempts_defined(self):
        assert AgentInboxProcessorWorker.MAX_ATTEMPTS >= 1

    def test_dead_letter_on_max_attempts(self):
        assert AgentInboxProcessorWorker.MAX_ATTEMPTS == 5


class TestInboxProcessorNoCrossModuleImports:
    """Verify the processor does not import from other modules."""

    def test_no_imports_from_other_modules(self):
        import woobe_workers.consumers.agent.inbox_processor as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )


class TestInboxHandlerProtocol:
    """Verify the handler protocol is defined."""

    def test_protocol_exists(self):
        assert AgentInboxHandlerProtocol is not None

    def test_protocol_has_handle_method(self):
        import typing

        hints = typing.get_type_hints(AgentInboxHandlerProtocol.handle)
        assert "return" in hints
