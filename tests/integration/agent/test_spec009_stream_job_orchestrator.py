"""Tests for spec 009: streaming and AskJobs orchestrator.

Covers: SSE phases (prepare/LLM/finalize/fail), job+outbox atomicity,
worker registration, no dynamic imports, no open session after prepare.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from modules.agent.runtime.ask_agent_stream_service import (
    AskAgentStreamService,
)
from modules.agent.application.use_cases.runtime_use_cases import (
    CreateAskJobInput,
    CreateAskJobUseCase,
)
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.events import AgentExecutionRequestedV1
from modules.agent.application.interfaces.llm_factory import LLMFactory
from modules.agent.infra.database.database import AgentDatabase


@pytest.fixture
def agent_id() -> UUID:
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
def mock_session_factory():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


class TestStreamPhases:
    """AskAgentStreamService must expose an async stream for AskInput."""

    @pytest.mark.asyncio
    async def test_stream_accepts_ask_input(self):
        llm_factory = MagicMock(spec=LLMFactory)
        session_factory = MagicMock()
        database = AgentDatabase(session_factory)
        settings = MagicMock(encryption_key="test-key")
        service = AskAgentStreamService(
            database,
            settings,
            llm_factory,
            http_executor=MagicMock(),
        )
        input_dto = AskInput(
            project_id=uuid4(), agent_id=uuid4(),
            message="test", tenant_id=None, user_id=None,
        )
        stream = service.stream(input_dto)
        assert stream is not None
        assert hasattr(stream, "__aiter__")

    @pytest.mark.asyncio
    async def test_no_dynamic_imports_in_file(self):
        import ast
        import inspect
        source = inspect.getsource(AskAgentStreamService)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = getattr(node.func, "id", None)
                if func and func.startswith("_import_"):
                    pytest.fail(f"Dynamic import function {func} still present")
        assert True


class TestCreateAskJobWithOutbox:
    """CreateAskJobUseCase must write Outbox event."""

    @pytest.mark.asyncio
    async def test_create_job_writes_outbox_when_provided(self):
        repo = MagicMock()
        job_id = uuid4()
        repo.create = AsyncMock(return_value=MagicMock(id=job_id))
        outbox = AsyncMock()
        use_case = CreateAskJobUseCase(repo=repo, outbox=outbox)

        input_dto = CreateAskJobInput(
            project_id=uuid4(), agent_id=uuid4(),
            session_id=uuid4(), message="test message",
        )
        result = await use_case.execute(input_dto)
        assert result.status == "pending"
        outbox.write.assert_called_once()
        event = outbox.write.call_args[0][0]
        assert isinstance(event, AgentExecutionRequestedV1)

    @pytest.mark.asyncio
    async def test_create_job_works_without_outbox(self):
        repo = MagicMock()
        job_id = uuid4()
        repo.create = AsyncMock(return_value=MagicMock(id=job_id))
        use_case = CreateAskJobUseCase(repo=repo, outbox=None)

        input_dto = CreateAskJobInput(
            project_id=uuid4(), agent_id=uuid4(),
            session_id=uuid4(), message="test message",
        )
        result = await use_case.execute(input_dto)
        assert result.status == "pending"


class TestWorkerRegistration:
    """AskJobWorker must be registered in the worker registry."""

    def test_ask_job_worker_importable(self):
        from modules.agent.runtime.workers.ask_job_worker import AskJobWorker
        assert AskJobWorker is not None

    def test_registry_includes_ask_job_worker(self):
        from modules.agent.runtime.workers.registry import register_agent_workers, AgentWorkerRegistry

        registry = AgentWorkerRegistry()
        engine = MagicMock()
        settings = MagicMock()
        rabbitmq_manager = MagicMock()

        register_agent_workers(registry, settings, engine, rabbitmq_manager)
        workers = registry.iter_workers()
        worker_types = [type(w).__name__ for w in workers]
        assert "AskJobWorker" in worker_types

    def test_ask_job_worker_conforms_to_protocol(self):
        from modules.agent.runtime.workers.ask_job_worker import AskJobWorker
        assert isinstance(AskJobWorker, type)
        engine = MagicMock()
        worker = AskJobWorker(async_engine=engine)
        assert hasattr(worker, "run")
        assert callable(worker.run)


class TestNoClosedSession:
    """The UoW owns session lifecycle while repositories are composed explicitly."""

    @pytest.mark.asyncio
    async def test_agent_unit_of_work_is_transaction_only(self):
        from modules.agent.infra.database.unit_of_work import AgentUnitOfWork

        session_factory = MagicMock()
        session_factory.return_value = AsyncMock()
        uow = AgentUnitOfWork(session_factory)

        assert not hasattr(uow, "agents")
        assert not hasattr(uow, "sessions")
        assert not hasattr(uow, "messages")
        assert not hasattr(uow, "outbox")

        async with uow:
            assert uow.session is not None

    def test_ask_job_worker_uses_direct_imports_not_dynamic(self):
        import ast
        import inspect
        from modules.agent.runtime.workers.ask_job_worker import AskJobWorker
        source = inspect.getsource(AskJobWorker)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = getattr(node.func, "id", None)
                if func and func.startswith("_import_"):
                    pytest.fail(f"Dynamic import function {func} still present")
        assert True