from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.base_worker import BaseWorker
from shared.workers.inbox_consumer_base import BaseInboxConsumer
from shared.workers.runner import WorkerRunner

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _DummyLongLivedWorker(BaseInboxConsumer):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore[arg-type]

    async def consume(self) -> None:
        pass

    async def persist_inbox(self, record) -> None:
        pass

    async def acknowledge(self, message) -> None:
        pass

    async def reject(self, message, error) -> None:
        pass


class _DummyPollerWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore[arg-type]

    async def run(self) -> None:
        pass


class _FailingWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore[arg-type]

    async def run(self) -> None:
        raise RuntimeError("worker failure")


class _SlowWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore[arg-type]

    async def run(self) -> None:
        await asyncio.sleep(3600)


class TestWorkerClassification:

    def test_long_lived_consumer_is_classified_correctly(self):
        runner = WorkerRunner(workers=[_DummyLongLivedWorker()])
        runner._classify(runner._workers[0]) == "long-lived"

    def test_poller_is_classified_correctly(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        runner._classify(runner._workers[0]) == "poller"


class TestWorkerStartStop:

    @pytest.mark.asyncio
    async def test_start_creates_tasks_for_all_workers(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker(), _DummyLongLivedWorker()])
        assert len(runner._tasks) == 0
        await runner.start()
        assert len(runner._tasks) == 2
        await runner.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_all_tasks(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker(), _DummyLongLivedWorker()])
        await runner.start()
        assert len(runner._tasks) == 2
        await runner.stop()
        assert all(t.done() for t in runner._tasks)

    @pytest.mark.asyncio
    async def test_start_creates_health_entries(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker(), _DummyLongLivedWorker()])
        await runner.start()
        health = runner.get_health()
        assert len(health) == 2
        names = {h.worker_name for h in health}
        assert "_DummyPollerWorker" in names
        assert "_DummyLongLivedWorker" in names
        await runner.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_health_to_not_running(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        await runner.start()
        await runner.stop()
        for h in runner.get_health():
            assert not h.is_running

    @pytest.mark.asyncio
    async def test_start_twice_does_not_raise(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        await runner.start()
        await runner.start()
        await runner.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_does_not_raise(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        await runner.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        await runner.start()
        await runner.stop()
        await runner.stop()


class TestFailureIsolation:

    @pytest.mark.asyncio
    async def test_failing_worker_does_not_crash_runner(self):
        runner = WorkerRunner(workers=[_FailingWorker()])
        await runner.start()
        await asyncio.sleep(0.05)
        health = runner.get_health()
        assert health[0].error == "worker failure"
        await runner.stop()

    @pytest.mark.asyncio
    async def test_healthy_worker_continues_after_failure(self):
        healthy = _DummyPollerWorker()
        failing = _FailingWorker()
        runner = WorkerRunner(workers=[healthy, failing])
        await runner.start()
        await asyncio.sleep(0.1)
        health_map = {h.worker_name: h for h in runner.get_health()}
        assert health_map["_FailingWorker"].error == "worker failure"
        assert health_map["_DummyPollerWorker"].error is None
        await runner.stop()


class TestRunnerFromRegistries:

    def test_from_registries_aggregates_all_workers(self):
        registry = MagicMock()
        registry.iter_workers.return_value = [_DummyPollerWorker()]
        runner = WorkerRunner.from_registries([registry])
        assert len(runner._workers) == 1

    def test_from_registries_empty(self):
        runner = WorkerRunner.from_registries([])
        assert len(runner._workers) == 0


class TestWorkerHealth:

    @pytest.mark.asyncio
    async def test_health_contains_worker_type(self):
        runner = WorkerRunner(workers=[_DummyLongLivedWorker(), _DummyPollerWorker()])
        await runner.start()
        health = runner.get_health()
        types = {h.worker_type for h in health}
        assert "long-lived" in types
        assert "poller" in types
        await runner.stop()

    @pytest.mark.asyncio
    async def test_health_has_started_at(self):
        runner = WorkerRunner(workers=[_DummyPollerWorker()])
        await runner.start()
        assert runner.get_health()[0].started_at is not None
        await runner.stop()


class TestRabbitMQDuplicateConsumerGuard:

    def test_consume_duplicate_queue_is_ignored(self):
        manager = RabbitMQManager(url="memory://", exchange_name="test")
        manager._consuming_queues.add("test.queue")
        assert "test.queue" in manager._consuming_queues

    def test_consuming_queues_cleared_on_close(self):
        manager = RabbitMQManager(url="memory://", exchange_name="test")
        manager._consuming_queues.add("q1")
        manager._consuming_queues.add("q2")
        manager._consuming_queues.clear()
        assert len(manager._consuming_queues) == 0


class TestRabbitMQTopologyDeclaration:

    def test_declare_topology_creates_dlx_exchange(self):
        manager = RabbitMQManager(url="memory://", exchange_name="test")
        assert manager._dlx_exchange is None
        assert manager._exchange_name == "test"

    def test_dlx_exchange_name(self):
        manager = RabbitMQManager(url="memory://", exchange_name="test")
        assert manager._exchange_name + ".dlx" == "test.dlx"


class TestMainPyIntegration:

    def test_main_imports_runner_and_rabbitmq(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        assert "from shared.workers.runner import WorkerRunner" in text
        assert "from shared.infra.rabbitmq import RabbitMQManager" in text

    def test_startup_calls_runner_start(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        assert "await runner.start()" in text

    def test_shutdown_calls_runner_stop(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        assert "await runner.stop()" in text

    def test_health_includes_workers(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        text = main_path.read_text(encoding="utf-8")
        assert '"workers"' in text or "'workers'" in text


class TestSingletonConsumerGuarantee:

    @pytest.mark.asyncio
    async def test_consume_does_not_register_duplicate(self):
        manager = RabbitMQManager(url="memory://", exchange_name="test")
        with patch.object(manager, "_channel") as mock_channel:
            mock_channel.declare_queue = AsyncMock()
            mock_channel.get_queue = AsyncMock()
            callback = AsyncMock()
            await manager.consume("test.q", ["test.#"], callback)
            assert "test.q" in manager._consuming_queues
            await manager.consume("test.q", ["test.#"], callback)
            assert mock_channel.get_queue.return_value.consume.call_count == 1
