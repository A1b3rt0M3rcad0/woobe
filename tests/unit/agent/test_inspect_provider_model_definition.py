import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.use_cases.inspect_provider_model_definition import (
    InspectProviderModelDefinitionUseCase,
)
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.enums import Provider, ProviderModelStatus
from shared.contracts.errors import ValidationError


def scenario():
    credential = ProviderCredential(
        project_id=uuid4(), provider=Provider.openai_compatible
    )

    class Credentials:
        async def get_by_id(self, identifier):
            return credential if identifier == credential.id else None

    class Models:
        items = []
        writes = 0

        async def list_by_credential(self, identifier):
            assert identifier == credential.id
            return self.items

        async def save(self, item):
            self.writes += 1
            return item

    models = Models()
    definition = CreateProviderModelInput(
        project_id=credential.project_id,
        provider_credential_id=credential.id,
        name="Imported",
        model="fake-language",
        model_type="language",
    )
    creator = CreateProviderModelUseCase(models, Credentials())
    inspector = InspectProviderModelDefinitionUseCase(creator, models)
    return models, creator, inspector, definition


def test_plan_is_read_only_and_reuses_only_a_full_equivalent_spec():
    async def check():
        models, creator, inspector, definition = scenario()
        candidate, _ = await creator.prepare(definition)
        candidate.name = "A different display name"
        wrong_project = deepcopy(candidate)
        wrong_project.project_id = uuid4()
        inactive = deepcopy(candidate)
        inactive.status = ProviderModelStatus.inactive
        corrupt = deepcopy(candidate)
        corrupt.spec_hash = "0" * 64
        altered = deepcopy(candidate)
        altered.spec["pricing"] = {"currency": "BRL"}
        altered.spec_hash = None
        models.items = [wrong_project, inactive, corrupt, altered, candidate]
        result = await inspector.execute(definition)
        assert result["existing_model_id"] == str(candidate.id)
        assert result["spec_hash"] == candidate.spec_hash
        assert models.writes == 0
        assert "encrypted_secret" not in result

    asyncio.run(check())


def test_plan_rejects_a_spec_for_a_different_provider_identity():
    async def check():
        models, creator, inspector, definition = scenario()
        proposed, _ = await creator.prepare(definition)
        definition.spec = deepcopy(proposed.spec)
        definition.spec["provider"] = "anthropic"
        with pytest.raises(ValidationError, match="identity"):
            await inspector.execute(definition)
        assert models.writes == 0

    asyncio.run(check())
