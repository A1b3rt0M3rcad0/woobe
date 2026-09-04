from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import CreateAskJobInput
from modules.agent.application.use_cases.runtime_use_cases import (
    CreateAskJobUseCase,
    GetPublicAskJobUseCase,
)
from modules.agent.domain.entities import AskJob
from modules.agent.domain.errors import AskJobNotFoundError
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicGetJobController,
)
from shared.presentation.contracts import OperationRequest
from shared.security.principal import ProjectApiPrincipal


def runtime_principal(environment: str) -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=uuid4(),
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=uuid4(),
        environment=environment,
        interfaces=frozenset({"jobs"}),
        authenticated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_job_persists_optional_caller_context() -> None:
    repo = SimpleNamespace(create=AsyncMock(side_effect=lambda job: job))
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = CreateAskJobUseCase(repo, outbox)
    input_dto = CreateAskJobInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="Process this",
        tenant_id="tenant-123",
        user_id="user-456",
        metadata={"channel": "whatsapp"},
        execution_context="staging",
    )

    await use_case.execute(input_dto)

    saved = repo.create.await_args.args[0]
    assert saved.params["tenant_id"] == "tenant-123"
    assert saved.params["user_id"] == "user-456"
    assert saved.params["metadata"] == {"channel": "whatsapp"}
    assert saved.params["execution_context"] == "staging"


@pytest.mark.asyncio
async def test_sessionless_jobs_generate_distinct_event_idempotency_keys() -> None:
    repo = SimpleNamespace(create=AsyncMock(side_effect=lambda job: job))
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = CreateAskJobUseCase(repo, outbox)
    base = {
        "project_id": uuid4(),
        "agent_id": uuid4(),
        "message": "Process this",
        "execution_context": "production",
    }

    await use_case.execute(CreateAskJobInput(**base))
    await use_case.execute(CreateAskJobInput(**base))

    first_event = outbox.write.await_args_list[0].args[0]
    second_event = outbox.write.await_args_list[1].args[0]
    assert first_event.idempotency_key != second_event.idempotency_key


@pytest.mark.asyncio
async def test_job_polling_isolated_by_runtime_key_environment() -> None:
    principal = runtime_principal("production")
    job = AskJob(
        project_id=principal.project_id,
        agent_id=principal.agent_id,
        status="pending",
        params={"execution_context": "staging"},
    )
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=job))
    use_case = GetPublicAskJobUseCase(repo)
    controller = PublicGetJobController(use_case)
    request = OperationRequest(
        principal=principal,
        path_params={"job_id": str(job.id)},
    )

    with pytest.raises(AskJobNotFoundError):
        await controller.handle(request)

