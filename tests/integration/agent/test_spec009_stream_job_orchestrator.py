"""Tests for spec 009: streaming and AskJobs orchestrator.

Covers: SSE phases (prepare/LLM/finalize/fail), job+outbox atomicity,
worker registration, no dynamic imports, no open session after prepare.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from modules.agent.infra.execution.ask_agent_stream_service import (
    AskAgentStreamService,
)
from modules.agent.application.use_cases.runtime_use_cases import (
    CreateAskJobInput,
    CreateAskJobUseCase,
)
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.events import AgentExecutionRequestedV1


@pytest.fixture
def agent_id() -> UUID:
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


class TestStreamPhases:
    """AskAgentStreamService must expose an async stream for AskInput."""

    @pytest.mark.asyncio
    async def test_stream_accepts_ask_input(self):
        service = AskAgentStreamService(
            use_case=MagicMock(),
            transactions=MagicMock(),
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
    async def test_create_job_persists_external_context_for_worker_roundtrip(self):
        repo = MagicMock()
        job_id = uuid4()
        captured = {}

        async def _create(job):
            captured["job"] = job
            job.id = job_id
            return job

        repo.create = AsyncMock(side_effect=_create)
        use_case = CreateAskJobUseCase(repo=repo, outbox=None)

        await use_case.execute(
            CreateAskJobInput(
                project_id=uuid4(),
                agent_id=uuid4(),
                message="test message",
                execution_context="playground",
                external_context={"age": 18},
            )
        )

        assert captured["job"].params["external_context"] == {"age": 18}
        assert captured["job"].params["execution_context"] == "playground"


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
        from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker
        assert AskJobWorker is not None

    def test_registry_includes_ask_job_worker(self):
        from woobe_workers.consumers.agent.registry import register_agent_workers, AgentWorkerRegistry

        registry = AgentWorkerRegistry()
        engine = MagicMock()
        settings = MagicMock()
        rabbitmq_manager = MagicMock()

        register_agent_workers(registry, settings, engine, rabbitmq_manager)
        workers = registry.iter_workers()
        worker_types = [type(w).__name__ for w in workers]
        assert "AskJobWorker" in worker_types

    def test_ask_job_worker_conforms_to_protocol(self):
        from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker
        assert isinstance(AskJobWorker, type)
        engine = MagicMock()
        settings = MagicMock()
        worker = AskJobWorker(async_engine=engine, settings=settings)
        assert hasattr(worker, "run")
        assert callable(worker.run)

    def test_ask_job_worker_forwards_external_context_into_runtime_input(self):
        import ast
        import inspect
        import textwrap

        from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker

        tree = ast.parse(textwrap.dedent(inspect.getsource(AskJobWorker._process_job)))
        ask_input_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AskInput"
        ]

        assert len(ask_input_calls) == 1
        keywords = {item.arg: item.value for item in ask_input_calls[0].keywords}
        assert "external_context" in keywords
        value = keywords["external_context"]
        assert isinstance(value, ast.Call)
        assert isinstance(value.func, ast.Attribute)
        assert value.func.attr == "get"
        assert isinstance(value.args[0], ast.Constant)
        assert value.args[0].value == "external_context"


    def test_ask_job_worker_resolves_context_manager_through_public_boundary(self):
        import ast
        import inspect

        from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker

        module = inspect.getmodule(AskJobWorker)
        assert module is not None
        module_tree = ast.parse(inspect.getsource(module))
        boundary_names = {
            alias.name
            for node in ast.walk(module_tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "modules.agent.background_boundary"
            for alias in node.names
        }
        assert "build_runtime_context_manager" in boundary_names
        assert "StandardContextManager" not in boundary_names

        tree = ast.parse(inspect.getsource(AskJobWorker))
        assembler_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "configure_context_manager"
        ]

        assert len(assembler_calls) == 1
        assert len(assembler_calls[0].args) == 1
        configured = assembler_calls[0].args[0]
        assert isinstance(configured, ast.Call)
        assert isinstance(configured.func, ast.Name)
        assert configured.func.id == "build_runtime_context_manager"
        assert len(configured.args) == 1
        assert isinstance(configured.args[0], ast.Attribute)
        assert configured.args[0].attr == "default_context_manager"


class TestNoClosedSession:
    """The UoW owns session lifecycle while repositories are composed explicitly."""

    @pytest.mark.asyncio
    async def test_agent_unit_of_work_is_transaction_only(self):
        from modules.agent.infra.database.unit_of_work import AgentUnitOfWork

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        uow = AgentUnitOfWork(engine)

        assert not hasattr(uow, "agents")
        assert not hasattr(uow, "sessions")
        assert not hasattr(uow, "messages")
        assert not hasattr(uow, "outbox")

        try:
            async with uow:
                assert uow.session is not None
        finally:
            await engine.dispose()

    def test_ask_job_worker_uses_direct_imports_not_dynamic(self):
        import ast
        import inspect
        from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker
        source = inspect.getsource(AskJobWorker)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = getattr(node.func, "id", None)
                if func and func.startswith("_import_"):
                    pytest.fail(f"Dynamic import function {func} still present")
        assert True
