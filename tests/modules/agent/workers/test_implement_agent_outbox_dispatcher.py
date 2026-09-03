"""Tests for spec 080 — implement agent outbox dispatcher."""
import ast
import inspect

from woobe_workers.consumers.agent.outbox_dispatcher import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentOutboxDispatcherWorker,
    AgentOutboxPublisherProtocol,
)
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher


class TestOutboxDispatcherStructure:
    """Verify the dispatcher is properly located and inherits from the base."""

    def test_file_exists_in_correct_location(self):
        import woobe_workers.consumers.agent.outbox_dispatcher as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/workers" in mod.__file__.replace("\\", "/")

    def test_inherits_from_base_outbox_dispatcher(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)

    def test_implements_claim_pending(self):
        assert hasattr(AgentOutboxDispatcherWorker, "claim_pending")

    def test_implements_publish(self):
        assert hasattr(AgentOutboxDispatcherWorker, "publish")

    def test_implements_mark_published(self):
        assert hasattr(AgentOutboxDispatcherWorker, "mark_published")

    def test_implements_mark_dead(self):
        assert hasattr(AgentOutboxDispatcherWorker, "mark_dead")

    def test_implements_mark_retryable(self):
        assert hasattr(AgentOutboxDispatcherWorker, "mark_retryable")


class TestOutboxDispatcherDelegation:
    """Verify the dispatcher delegates to repository and publisher."""

    def test_claim_pending_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in source

    def test_publish_uses_publisher_protocol(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "_publisher" in source
        assert "publish" in source

    def test_publish_converts_to_rabbit_message(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "outbox_to_rabbit_message" in source

    def test_mark_published_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_published)
        assert "mark_published" in source

    def test_mark_dead_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_dead)
        assert "mark_dead" in source

    def test_mark_retryable_uses_repository(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "mark_retryable" in source


class TestOutboxDispatcherRetryBackoff:
    """Verify retry backoff is implemented."""

    def test_retry_backoff_constant_defined(self):
        assert isinstance(RETRY_BACKOFF_BASE_SECONDS, int)
        assert RETRY_BACKOFF_BASE_SECONDS > 0

    def test_mark_retryable_uses_backoff(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "RETRY_BACKOFF_BASE_SECONDS" in source or "backoff" in source

    def test_mark_retryable_calculates_available_at(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "available_at" in source


class TestOutboxDispatcherConcurrency:
    """Verify concurrency safety patterns."""

    def test_claim_pending_uses_locked_by(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "locked_by" in source

    def test_worker_has_unique_id(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.__init__)
        assert "worker_id" in source

    def test_run_manages_session_lifecycle(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.run)
        assert "AsyncSession" in source
        assert "begin" in source


class TestOutboxDispatcherNoCrossModuleImports:
    """Verify the dispatcher does not import from other modules."""

    def test_no_imports_from_other_modules(self):
        import woobe_workers.consumers.agent.outbox_dispatcher as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )


class TestOutboxPublisherProtocol:
    """Verify the publisher protocol is defined."""

    def test_protocol_exists(self):
        assert AgentOutboxPublisherProtocol is not None

    def test_protocol_has_publish_method(self):
        import typing

        hints = typing.get_type_hints(AgentOutboxPublisherProtocol.publish)
        assert "return" in hints
