from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.use_cases.provider_model_reconciliation import (
    PreviewProviderModelReconciliationUseCase,
    ApplyProviderModelReconciliationUseCase,
    ReconciliationScope,
    ApplyProviderModelReconciliationInput,
)
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.enums import CredentialStatus
from modules.agent.infra.adapters.provider_discovery_adapters import (
    _spec_to_available_output,
)
from shared.contracts.errors import ConflictError
from tests.unit.agent.test_model_provider_runtime_regressions import _language_spec


class Models:
    def __init__(self):
        self.items = []
        self.writes = 0
        self.observations = 0

    async def list_by_credential(self, identifier):
        return list(self.items)

    async def lock_by_id(self, identifier):
        return next(
            (deepcopy(item) for item in self.items if item.id == identifier), None
        )

    async def save(self, item):
        self.items.append(deepcopy(item))
        self.writes += 1
        return item

    async def record_catalog_observation(self, identifier, evidence):
        item = next(item for item in self.items if item.id == identifier)
        item.metadata = {
            **(item.metadata or {}),
            "catalog_observation": deepcopy(evidence),
        }
        self.observations += 1


def scenario():
    credential = ProviderCredential(project_id=uuid4(), provider="openai")

    class Credentials:
        async def lock_by_id(self, identifier):
            return credential if credential.id == identifier else None

    models = Models()
    scope = ReconciliationScope(
        project_id=credential.project_id, provider_credential_id=credential.id
    )
    spec = _language_spec()
    remote = [_spec_to_available_output(spec, provider="openai")]
    return credential, Credentials(), models, scope, remote


def selection_dto(scope, preview):
    return ApplyProviderModelReconciliationInput(
        **scope.model_dump(),
        expected_credential_revision=preview["expected_credential_revision"],
        selections=[
            {
                key: preview["items"][0].get(key)
                for key in (
                    "model_id",
                    "installed_model_id",
                    "expected_model_revision",
                    "candidate_digest",
                )
            }
        ],
    )


@pytest.mark.asyncio
async def test_preview_is_read_only_and_repeated_apply_reuses_definition():
    credential, credentials, models, scope, remote = scenario()
    preview = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, remote
    )
    assert preview["items"][0]["state"] == "new" and models.writes == 0
    dto = selection_dto(scope, preview)
    use_case = ApplyProviderModelReconciliationUseCase(models, credentials)
    first = await use_case.execute(dto, remote, credential.binding_revision)
    retry = await use_case.execute(dto, remote, credential.binding_revision)
    assert models.writes == 1
    assert (
        first["items"][0]["provider_model_id"] == retry["items"][0]["provider_model_id"]
    )
    assert retry["items"][0]["result"] == "reused"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["catalog", "credential", "configuration"])
async def test_apply_refuses_changed_evidence_before_any_write(change):
    credential, credentials, models, scope, remote = scenario()
    preview = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, remote
    )
    dto = selection_dto(scope, preview)
    if change == "catalog":
        remote[0].raw["changed_after_preview"] = True
    elif change == "credential":
        credential.status = CredentialStatus.revoked
    with pytest.raises(ConflictError):
        await ApplyProviderModelReconciliationUseCase(models, credentials).execute(
            dto,
            remote,
            credential.binding_revision,
            "rotated" if change == "configuration" else None,
        )
    assert models.writes == 0


@pytest.mark.asyncio
async def test_price_change_creates_candidate_and_keeps_installed_snapshot():
    credential, credentials, models, scope, remote = scenario()
    installed = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=scope.project_id,
            provider_credential_id=credential.id,
            name="Published",
            model="gpt-test",
            spec=replace(
                _language_spec(), pricing={"input_cost_per_1m_tokens": 1}
            ).as_dict(),
        ),
        credential,
    )
    models.items.append(installed)
    original = deepcopy(installed.spec)
    remote[0] = _spec_to_available_output(
        replace(_language_spec(), pricing={"input_cost_per_1m_tokens": 2}),
        provider="openai",
    )
    preview = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, remote
    )
    assert preview["items"][0]["change_kind"] == "pricing_changed"
    result = await ApplyProviderModelReconciliationUseCase(models, credentials).execute(
        selection_dto(scope, preview), remote, credential.binding_revision
    )
    assert result["items"][0]["provider_model_id"] != str(installed.id)
    assert installed.spec == original
    missing = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, []
    )
    assert all(item["state"] == "not_discovered" for item in missing["items"])
    assert len(models.items) == 2


@pytest.mark.asyncio
async def test_manual_override_survives_catalog_refresh_and_local_revision_conflicts():
    credential, credentials, models, scope, remote = scenario()
    installed = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=scope.project_id,
            provider_credential_id=credential.id,
            name="Manual",
            model="gpt-test",
            spec=_language_spec().as_dict(),
            metadata={
                "model_spec_overrides": {"capabilities": {"tool_calling": False}}
            },
        ),
        credential,
    )
    models.items.append(installed)
    preview = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, remote
    )
    assert preview["items"][0]["state"] == "manually_overridden"
    assert (
        preview["items"][0]["proposed_spec"]["capabilities"]["tool_calling"][
            "supported"
        ]
        is False
    )
    installed.metadata["changed"] = True
    with pytest.raises(ConflictError, match="changed"):
        await ApplyProviderModelReconciliationUseCase(models, credentials).execute(
            selection_dto(scope, preview), remote, credential.binding_revision
        )
    assert models.writes == 0


@pytest.mark.asyncio
async def test_provenance_refresh_preserves_definition_and_retry_preconditions():
    credential, credentials, models, scope, remote = scenario()
    installed = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=scope.project_id,
            provider_credential_id=credential.id,
            name="Published",
            model="gpt-test",
            spec=_language_spec().as_dict(),
        ),
        credential,
    )
    models.items.append(installed)
    original = deepcopy(installed.spec)
    remote[0] = _spec_to_available_output(
        replace(
            _language_spec(),
            metadata={"provider_model_raw": {"description": "New evidence"}},
        ),
        provider="openai",
    )
    preview = await PreviewProviderModelReconciliationUseCase(models).execute(
        scope, credential, remote
    )
    assert preview["items"][0]["change_kind"] == "provenance_only_changed"
    dto = selection_dto(scope, preview)
    use_case = ApplyProviderModelReconciliationUseCase(models, credentials)
    first = await use_case.execute(dto, remote, credential.binding_revision)
    retry = await use_case.execute(dto, remote, credential.binding_revision)
    assert first["items"][0]["evidence_updated"] is True
    assert retry["items"][0]["evidence_updated"] is False
    assert models.writes == 0 and models.observations == 1
    assert installed.spec == original
