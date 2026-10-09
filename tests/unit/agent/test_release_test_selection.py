from contextlib import asynccontextmanager
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database import release_test_execution_store as store_module
from modules.agent.infra.database.release_test_execution_store import (
    SQLReleaseTestExecutionStore,
)
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


def test_agent_patch_rejects_unknown_fields_instead_of_dropping_them():
    from pydantic import ValidationError as InputValidationError
    from modules.agent.entrypoint import UpdateAgentInput

    assert UpdateAgentInput.model_json_schema()["additionalProperties"] is False
    with pytest.raises(InputValidationError):
        UpdateAgentInput.model_validate(
            {"name": "Support", "unexpected_audit_field": True}
        )
    assert UpdateAgentInput.model_validate({"name": "Support"}).name == "Support"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [True, None])
async def test_public_agent_patch_controller_rejects_unknown_keys_before_mutation(
    value,
):
    from pydantic import ValidationError as InputValidationError
    from modules.agent.presentation.controllers.update_agent_controller import (
        UpdateAgentController,
    )

    use_case = N(execute=AsyncMock())
    request = N(
        path_params={"agent_id": uuid4()},
        metadata={},
        body={"name": "Support", "unexpected_audit_field": value},
    )
    with pytest.raises(InputValidationError):
        await UpdateAgentController(use_case).handle(request)
    use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment,kind,selected,accepted",
    [
        ("staging", "release", True, True),
        ("production", "release", True, True),
        ("staging", "staging", False, True),
        ("production", "release", False, True),
        ("release", "release", False, True),
        ("draft", "draft", False, True),
        ("staging", "release", False, False),
        ("draft", "release", False, False),
        ("production", "staging", False, False),
        ("release", "staging", False, False),
    ],
)
async def test_release_test_preparation_respects_authoritative_environment_and_legacy_kind(
    monkeypatch, environment, kind, selected, accepted
):
    request = N(
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=uuid4(),
        environment=environment,
        message="ping",
        external_context=None,
        expected_output=None,
    )
    release = N(
        id=request.release_id,
        project_id=request.project_id,
        agent_id=request.agent_id,
        snapshot_kind=kind,
        contract_version_id=None,
    )
    session = N(get=AsyncMock(return_value=release))

    @asynccontextmanager
    async def uow():
        yield N(session=session)

    authority = AsyncMock()
    selector = AsyncMock(return_value=release if selected else None)
    repository = N(save=AsyncMock(side_effect=lambda entity: entity))
    monkeypatch.setattr(store_module, "authorize_export_read", authority)
    monkeypatch.setattr(store_module, "selected_agent_release", selector)
    monkeypatch.setattr(
        store_module, "SQLAlchemyAgentReleaseTestRepository", lambda _: repository
    )
    if accepted:
        result = await SQLReleaseTestExecutionStore(uow).prepare(request, "principal")
        assert result.release_id == request.release_id
    else:
        with pytest.raises(ValidationError):
            await SQLReleaseTestExecutionStore(uow).prepare(request, "principal")
        repository.save.assert_not_awaited()
    authority.assert_awaited_once()
    if environment in {"staging", "production"}:
        selector.assert_awaited_once_with(
            session, request.agent_id, environment, lock=True
        )
    else:
        selector.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_selection_cannot_record_test_against_another_release(
    monkeypatch,
):
    request = N(
        project_id=uuid4(), agent_id=uuid4(), release_id=uuid4(), environment="staging"
    )
    release = N(
        id=request.release_id, project_id=request.project_id, agent_id=request.agent_id
    )
    session = N(get=AsyncMock(return_value=release))

    @asynccontextmanager
    async def uow():
        yield N(session=session)

    monkeypatch.setattr(store_module, "authorize_export_read", AsyncMock())
    monkeypatch.setattr(
        store_module, "selected_agent_release", AsyncMock(return_value=N(id=uuid4()))
    )
    save = AsyncMock()
    monkeypatch.setattr(
        store_module, "SQLAlchemyAgentReleaseTestRepository", lambda _: N(save=save)
    )
    with pytest.raises(ConflictError, match="ASAC_TEST_SELECTION_CHANGED"):
        await SQLReleaseTestExecutionStore(uow).prepare(request, "principal")
    save.assert_not_awaited()
