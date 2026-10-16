import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from modules.agent.application.interfaces import project_configuration
from modules.agent.application.use_cases.provider_model_reconciliation import (
    ApplyProviderModelReconciliationInput,
    ApplyProviderModelReconciliationUseCase,
    PreviewProviderModelReconciliationUseCase,
    ReconciliationScope,
)
from modules.agent.domain.entities import AgentRelease, ProviderModel
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from modules.agent.infra.adapters.provider_discovery_adapters import (
    _spec_to_available_output,
)
from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    ProviderCredentialModel,
)
from modules.agent.infra.database.provider_model_repositories import (
    ProviderModelModel,
    SQLAlchemyProviderModelRepository,
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import ConflictError
from shared.infra.config import Settings
from shared.infra.database.session import create_engine
from tests.unit.agent.test_model_provider_runtime_regressions import _language_spec


@pytest.fixture
async def seeded(monkeypatch):
    # This fixture exercises owner SQL locking independently of configuration
    # authority, which has its own live acceptance suite.
    monkeypatch.setattr(project_configuration, "_factory", None)
    engine = create_engine(Settings.model_validate({}))
    if engine.dialect.name != "postgresql":
        await engine.dispose()
        pytest.skip("PostgreSQL test stack required")
    project_id, credential_id, agent_id = uuid4(), uuid4(), uuid4()
    spec = _language_spec()
    async with AgentUnitOfWork(engine) as uow:
        uow.session.add(
            ProviderCredentialModel(
                id=credential_id,
                project_id=project_id,
                provider="openai",
                name=str(credential_id),
                status="active",
                binding_revision=1,
            )
        )
        await uow.session.flush()
        model = await SQLAlchemyProviderModelRepository(uow).save(
            ProviderModel(
                project_id=project_id,
                provider_credential_id=credential_id,
                name="Model",
                model=spec.model_id,
                model_type=spec.model_type,
                spec=spec.as_dict(),
                spec_version=1,
                spec_hash=model_spec_hash(spec),
            )
        )
        uow.session.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                name="Test",
                type="assistant",
                system_prompt="",
                provider="openai",
                model=spec.model_id,
                provider_credential_id=credential_id,
                temperature=0.2,
                session_mode="stateful",
                status="active",
                settings={},
            )
        )
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        provider="openai",
        model=spec.model_id,
        provider_model_id=model.id,
        provider_credential_id=credential_id,
        session_mode="stateful",
        model_spec_snapshot=spec.as_dict(),
        model_spec_hash=model_spec_hash(spec),
    )
    try:
        yield engine, model, release
    finally:
        async with AgentUnitOfWork(engine) as uow:
            await uow.session.execute(
                delete(AgentReleaseModel).where(AgentReleaseModel.agent_id == agent_id)
            )
            await uow.session.execute(
                delete(AgentModel).where(AgentModel.id == agent_id)
            )
            await uow.session.execute(
                delete(ProviderModelModel).where(
                    ProviderModelModel.project_id == project_id
                )
            )
            await uow.session.execute(
                delete(ProviderCredentialModel).where(
                    ProviderCredentialModel.id == credential_id
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_published_identity_guards_roll_back_and_secret_rotation_remains_valid(
    seeded,
):
    engine, model, release = seeded
    async with AgentUnitOfWork(engine) as uow:
        await SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow).save(release)
    with pytest.raises(ConflictError) as error:
        async with AgentUnitOfWork(engine) as uow:
            repository = SQLAlchemyProviderModelRepository(uow)
            current = await repository.get_by_id(model.id)
            current.model = "different"
            current.name = "Must roll back"
            await repository.update(current)
    assert error.value.code == "MODEL_IDENTITY_IN_USE"
    with pytest.raises(ConflictError) as error:
        async with AgentUnitOfWork(engine) as uow:
            repository = SQLAlchemyProviderCredentialRepository(uow)
            credential = await repository.get_by_id(model.provider_credential_id)
            credential.provider = "anthropic"
            await repository.update(credential)
    assert error.value.code == "CREDENTIAL_IDENTITY_IN_USE"
    async with AgentUnitOfWork(engine) as uow:
        repository = SQLAlchemyProviderCredentialRepository(uow)
        credential = await repository.get_by_id(model.provider_credential_id)
        credential.encrypted_secret = "disposable-rotated-material"
        await repository.update(credential)
        unchanged = await SQLAlchemyProviderModelRepository(uow).get_by_id(model.id)
        assert unchanged.model == model.model and unchanged.name == model.name
        assert unchanged.spec_hash == model.spec_hash


@pytest.mark.asyncio
async def test_capture_racing_identity_change_rechecks_under_row_lock(seeded):
    engine, model, release = seeded
    ready, proceed = asyncio.Event(), asyncio.Event()

    async def retarget():
        async with AgentUnitOfWork(engine) as uow:
            repository = SQLAlchemyProviderModelRepository(uow)
            current = await repository.lock_by_id(model.id)
            spec = replace(ModelSpec.from_dict(current.spec), model_id="new-model")
            current.model, current.spec, current.spec_hash = (
                spec.model_id,
                spec.as_dict(),
                model_spec_hash(spec),
            )
            await repository.update(current)
            ready.set()
            await asyncio.wait_for(proceed.wait(), 5)

    async def capture():
        await ready.wait()
        async with AgentUnitOfWork(engine) as uow:
            await SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow).save(release)

    update = asyncio.create_task(retarget())
    capture_task = asyncio.create_task(capture())
    try:
        await asyncio.wait_for(ready.wait(), 5)
        await asyncio.sleep(0.05)
        assert not capture_task.done()
        proceed.set()
        await update
        with pytest.raises(ConflictError) as error:
            await capture_task
        assert error.value.code == "RELEASE_MODEL_BINDING_CONFLICT"
    finally:
        proceed.set()
        await asyncio.gather(update, capture_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_concurrent_apply_creates_one_definition_and_reuses_it(seeded):
    engine, model, _ = seeded
    remote = [
        _spec_to_available_output(
            replace(_language_spec(), model_id="new-model"), provider="openai"
        )
    ]
    scope = ReconciliationScope(
        project_id=model.project_id, provider_credential_id=model.provider_credential_id
    )
    async with AgentUnitOfWork(engine) as uow:
        credential = await SQLAlchemyProviderCredentialRepository(uow).get_by_id(
            model.provider_credential_id
        )
        preview = await PreviewProviderModelReconciliationUseCase(
            SQLAlchemyProviderModelRepository(uow)
        ).execute(scope, credential, remote)
    candidate = next(
        item for item in preview["items"] if item["model_id"] == "new-model"
    )
    dto = ApplyProviderModelReconciliationInput(
        **scope.model_dump(),
        expected_credential_revision=1,
        selections=[
            {
                key: candidate.get(key)
                for key in (
                    "model_id",
                    "installed_model_id",
                    "expected_model_revision",
                    "candidate_digest",
                )
            }
        ],
    )

    async def apply():
        async with AgentUnitOfWork(engine) as uow:
            return await ApplyProviderModelReconciliationUseCase(
                SQLAlchemyProviderModelRepository(uow),
                SQLAlchemyProviderCredentialRepository(uow),
            ).execute(dto, remote, 1)

    results = await asyncio.gather(apply(), apply())
    assert {result["items"][0]["result"] for result in results} == {"created", "reused"}
    async with AgentUnitOfWork(engine) as uow:
        assert (
            await uow.session.scalar(
                select(func.count())
                .select_from(ProviderModelModel)
                .where(
                    ProviderModelModel.project_id == model.project_id,
                    ProviderModelModel.model == "new-model",
                )
            )
            == 1
        )


@pytest.mark.asyncio
async def test_provenance_observation_keeps_definition_revision_and_retries_idempotently(
    seeded,
):
    from modules.agent.application.use_cases.provider_model_reconciliation import (
        model_revision,
    )

    engine, model, _ = seeded
    original_revision = model_revision(model)
    remote = [
        _spec_to_available_output(
            replace(
                _language_spec(),
                metadata={"provider_model_raw": {"description": "New evidence"}},
            ),
            provider="openai",
        )
    ]
    scope = ReconciliationScope(
        project_id=model.project_id, provider_credential_id=model.provider_credential_id
    )
    async with AgentUnitOfWork(engine) as uow:
        credential = await SQLAlchemyProviderCredentialRepository(uow).get_by_id(
            model.provider_credential_id
        )
        preview = await PreviewProviderModelReconciliationUseCase(
            SQLAlchemyProviderModelRepository(uow)
        ).execute(scope, credential, remote)
    candidate = preview["items"][0]
    assert candidate["change_kind"] == "provenance_only_changed"
    dto = ApplyProviderModelReconciliationInput(
        **scope.model_dump(),
        expected_credential_revision=1,
        selections=[
            {
                key: candidate.get(key)
                for key in (
                    "model_id",
                    "installed_model_id",
                    "expected_model_revision",
                    "candidate_digest",
                )
            }
        ],
    )
    for expected_update in (True, False):
        async with AgentUnitOfWork(engine) as uow:
            result = await ApplyProviderModelReconciliationUseCase(
                SQLAlchemyProviderModelRepository(uow),
                SQLAlchemyProviderCredentialRepository(uow),
            ).execute(dto, remote, 1)
            assert result["items"][0]["evidence_updated"] is expected_update
    async with AgentUnitOfWork(engine) as uow:
        current = await SQLAlchemyProviderModelRepository(uow).get_by_id(model.id)
        assert current.spec == model.spec and current.spec_hash == model.spec_hash
        assert model_revision(current) == original_revision
        assert (
            current.metadata["catalog_observation"]["model_spec"]
            == remote[0].model_spec
        )
