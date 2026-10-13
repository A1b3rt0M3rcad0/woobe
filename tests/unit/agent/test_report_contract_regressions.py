from copy import deepcopy
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import (
    CreateReleaseInput,
    UpdateContractInput,
)
from modules.agent.application.use_cases.ai_contract_cases import UpdateContractUseCase
from modules.agent.application.use_cases.execute_release_test import ExecuteReleaseTest
from modules.agent.application.use_cases.session_mode_compatible_release import (
    SessionModeCompatibleCreateReleaseUseCase,
)
from modules.agent.application.execution_snapshot import (
    apply_agent_execution_snapshot,
    build_agent_execution_snapshot,
)
from modules.agent.domain.entities import (
    Agent,
    AgentRelease,
    AgentContract,
    AgentPrompt,
)
from modules.agent.domain.enums import Provider
from shared.contracts.errors import ConflictError, ValidationError

SCHEMA = {
    "type": "object",
    "properties": {"message": {"type": "string", "minLength": 2}},
    "required": ["message"],
    "additionalProperties": False,
}


@pytest.mark.asyncio
async def test_patch_updates_existing_contract_and_checks_cas_before_mutation():
    item = AgentContract(version="1", updated_at=datetime.now(UTC))
    repo = N(
        get_by_id=AsyncMock(side_effect=lambda _: deepcopy(item)),
        update=AsyncMock(side_effect=lambda value, **kw: value),
        save=AsyncMock(),
    )
    result = await UpdateContractUseCase(repo).execute(
        item.id,
        UpdateContractInput(output_schema=SCHEMA, expected_updated_at=item.updated_at),
    )
    assert result.id == item.id and result.output_schema == SCHEMA
    assert (
        result.input_schema == {}
        and result.additional_instructions == ""
        and result.name == "Contract 1"
    )
    assert len(result.schema_hash) == 64
    repo.save.assert_not_awaited()
    assert repo.update.await_args.kwargs["expected_updated_at"] == item.updated_at
    with pytest.raises(ConflictError):
        await UpdateContractUseCase(repo).execute(
            item.id,
            UpdateContractInput(
                name="Stale", expected_updated_at=item.updated_at - timedelta(seconds=1)
            ),
        )
    assert repo.update.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("inline", [False, True])
async def test_reference_materialization_uses_exact_selected_prompt_and_contract(
    inline,
):
    agent = Agent(
        name="Support",
        model="fake",
        provider=Provider.openai,
        system_prompt="Old prompt",
    )
    prompt = AgentPrompt(
        project_id=agent.project_id,
        agent_id=agent.id,
        version="2",
        content="New exact version\n" + "A" * 1690,
    )
    contract = AgentContract(
        project_id=agent.project_id,
        agent_id=agent.id,
        version="2",
        output_schema=SCHEMA,
    )
    repo = N(
        get_by_id=AsyncMock(return_value=agent),
        update=AsyncMock(side_effect=lambda a: a),
    )
    delegate = N(execute=AsyncMock(side_effect=lambda dto, **kw: dto))
    saver = SessionModeCompatibleCreateReleaseUseCase(
        delegate,
        repo,
        prompt_repo=N(get_by_id=AsyncMock(return_value=prompt)),
        contract_repo=N(get_by_id=AsyncMock(return_value=contract)),
    )
    fields = {"system_prompt": "Old prompt"} if inline else {}
    dto = CreateReleaseInput(
        project_id=agent.project_id,
        agent_id=agent.id,
        version="draft",
        prompt_version_id=prompt.id,
        contract_version_id=contract.id,
        **fields,
    )
    if inline:
        with pytest.raises(ConflictError):
            await saver.execute(dto)
        delegate.execute.assert_not_awaited()
    else:
        saved = await saver.execute(dto)
        assert saved.system_prompt == prompt.content and saved.output_schema == SCHEMA
        assert (
            saved.response_format["schema"] == SCHEMA
            and saved.response_format["enabled"]
        )
        assert agent.system_prompt == prompt.content
        again = await saver.execute(
            CreateReleaseInput(
                project_id=agent.project_id, agent_id=agent.id, version="draft"
            )
        )
        assert (
            again.prompt_version_id == prompt.id
            and again.contract_version_id == contract.id
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result,valid",
    [
        ({"answer": '{"message":"yes"}'}, True),
        ({"answer": '{"other":"wrong"}'}, False),
        ({"answer": "not JSON"}, False),
        ({"parsed_output": {"message": ""}}, False),
        ({"parsed_output": {"message": "yes", "extra": 1}}, False),
    ],
)
async def test_passed_requires_effective_contract_validation_even_without_expected_output(
    result, valid
):
    store = N(
        prepare=AsyncMock(return_value=N(id=uuid4(), validation_schema=SCHEMA)),
        finish=AsyncMock(),
    )
    await ExecuteReleaseTest(store, N(run=AsyncMock(return_value=result))).execute(
        N(expected_output=None), "principal"
    )
    terminal = store.finish.await_args.kwargs
    assert terminal["actual_output"]["provider_completed"] is True
    assert terminal["actual_output"]["output_valid"] is valid
    assert terminal["errors"] == (
        [] if valid else [{"code": "OUTPUT_VALIDATION_FAILED"}]
    )


@pytest.mark.asyncio
async def test_missing_contract_never_executes_or_passes():
    store = N(
        prepare=AsyncMock(return_value=N(id=uuid4(), contract_missing=True)),
        finish=AsyncMock(),
    )
    runtime = N(run=AsyncMock())
    await ExecuteReleaseTest(store, runtime).execute(
        N(expected_output=None), "principal"
    )
    runtime.run.assert_not_awaited()
    assert store.finish.await_args.kwargs["errors"] == [{"code": "CONTRACT_MISSING"}]
    assert store.finish.await_args.kwargs["actual_output"]["contract_missing"] is True


@pytest.mark.asyncio
async def test_replayed_pending_test_never_repeats_provider_execution():
    pending = N(id=uuid4(), replayed=True, status="pending")
    runtime = N(run=AsyncMock())
    store = N(prepare=AsyncMock(return_value=pending), finish=AsyncMock())
    assert await ExecuteReleaseTest(store, runtime).execute(N(), "principal") is pending
    runtime.run.assert_not_awaited()
    store.finish.assert_not_awaited()


def test_runtime_rejects_legacy_missing_contract_without_looking_up_mutable_catalog():
    agent = Agent(name="Support", model="fake", provider=Provider.openai)
    release = AgentRelease(
        project_id=agent.project_id,
        agent_id=agent.id,
        model="fake",
        provider="openai",
        session_mode="stateless",
        contract_version_id=uuid4(),
    )
    with pytest.raises(ValidationError, match="CONTRACT_MISSING"):
        apply_agent_execution_snapshot(agent, build_agent_execution_snapshot(release))


@pytest.mark.asyncio
async def test_saved_contract_material_remains_frozen_after_native_contract_edit():
    agent = Agent(name="Support", model="fake", provider=Provider.openai)
    contract = AgentContract(
        project_id=agent.project_id,
        agent_id=agent.id,
        version="2",
        name="Output",
        output_schema=SCHEMA,
        additional_instructions="Original",
    )
    saver = SessionModeCompatibleCreateReleaseUseCase(
        N(execute=AsyncMock(side_effect=lambda dto, **kw: dto)),
        N(
            get_by_id=AsyncMock(return_value=agent),
            update=AsyncMock(side_effect=lambda a: a),
        ),
        contract_repo=N(get_by_id=AsyncMock(return_value=contract)),
    )
    saved = await saver.execute(
        CreateReleaseInput(
            project_id=agent.project_id,
            agent_id=agent.id,
            version="draft",
            contract_version_id=contract.id,
        )
    )
    contract.output_schema = {"type": "array"}
    contract.additional_instructions = "Changed"
    frozen = saved.runtime_config["contract_version_snapshot"]
    assert (
        frozen["output_schema"] == SCHEMA
        and frozen["additional_instructions"] == "Original"
    )
    assert saved.output_schema == SCHEMA


@pytest.mark.asyncio
async def test_native_test_wrapper_preserves_strict_rejection_evidence_and_resets_context():
    from modules.agent.application.interfaces.release_test_execution import (
        release_test_output_capture,
    )
    from modules.agent.infra.execution.release_test_runtime import (
        NativeReleaseTestRuntime,
    )

    captured = []

    async def rejection(request):
        captured.append(request.body)
        release_test_output_capture.get().update(
            answer='{"wrong":true}',
            parsed_output={"wrong": True},
            run_id="run",
            output_parse_error="OUTPUT_VALIDATION_FAILED",
        )
        return N(outcome=N(value="failure"), body={"success": False})

    snapshot = {"system_prompt": "Frozen selected prompt", "output_schema": SCHEMA}
    request = N(
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=uuid4(),
        message="Test",
        environment="draft",
        external_context=None,
    )
    result = await NativeReleaseTestRuntime(rejection).run(
        request, None, uuid4(), snapshot=snapshot
    )
    assert (
        captured[0]["loaded_release_id"] is None
        and captured[0]["snapshot_override"] == snapshot
    )
    assert result["output_parse_error"] == "OUTPUT_VALIDATION_FAILED" and result[
        "parsed_output"
    ] == {"wrong": True}
    assert release_test_output_capture.get() is None


def test_remote_json_schema_references_are_rejected_without_fetching():
    from modules.agent.application.use_cases.structured_output_contract import (
        validate_output_against_contract,
    )

    errors = validate_output_against_contract(
        {"value": 1}, {"$ref": "https://127.0.0.1/private-schema"}
    )
    assert errors and errors[0].path == "$"


@pytest.mark.asyncio
async def test_inline_schema_is_preserved_on_later_draft_save_and_adopts_deliberate_edit():
    agent = Agent(
        name="Support",
        model="fake",
        provider=Provider.openai,
        settings={"output_schema": SCHEMA},
    )
    saver = SessionModeCompatibleCreateReleaseUseCase(
        N(execute=AsyncMock(side_effect=lambda dto, **kw: dto)),
        N(
            get_by_id=AsyncMock(return_value=agent),
            update=AsyncMock(side_effect=lambda a: a),
        ),
    )
    dto = CreateReleaseInput(
        project_id=agent.project_id, agent_id=agent.id, version="draft"
    )
    saved = await saver.execute(dto)
    assert saved.output_schema == SCHEMA
    changed = {"type": "object", "properties": {"new": {"type": "string"}}}
    edited = await saver.execute(dto.model_copy(update={"output_schema": changed}))
    assert (
        edited.output_schema == changed and edited.response_format["schema"] == changed
    )
