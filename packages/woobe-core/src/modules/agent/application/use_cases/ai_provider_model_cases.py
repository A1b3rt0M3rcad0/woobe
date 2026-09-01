from __future__ import annotations

from uuid import UUID

from modules.agent.application.dtos.ai_dtos import (
    CreateProviderModelInput,
    ListProviderModelsInput,
    ProviderModelOutput,
    UpdateProviderModelInput,
)
from modules.agent.application.interfaces.provider_model_repository import (
    ProviderModelRepository,
)
from modules.agent.application.interfaces.repositories import ProviderCredentialRepository
from modules.agent.domain.entities import ProviderModel
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from shared.contracts.errors import ValidationError


class CreateProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(self, input_dto: CreateProviderModelInput) -> ProviderModelOutput:
        credential = await self._load_active_credential(
            input_dto.provider_credential_id,
            input_dto.project_id,
        )
        item = ProviderModel(
            project_id=input_dto.project_id,
            provider_credential_id=input_dto.provider_credential_id,
            name=input_dto.name.strip(),
            model=input_dto.model.strip(),
            metadata=input_dto.metadata or {},
            status=ProviderModelStatus.active,
        )
        if not item.name:
            raise ValidationError("Provider model name is required")
        if not item.model:
            raise ValidationError("Provider model identifier is required")
        saved = await self._provider_model_repo.save(item)
        return _provider_model_to_output(saved, credential.provider)

    async def _load_active_credential(self, credential_id: UUID, project_id: UUID):
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None or credential.project_id != project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        status = getattr(credential.status, "value", credential.status)
        if status != CredentialStatus.active.value:
            raise ValidationError("Provider credential must be active")
        return credential


class UpdateProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(
        self,
        provider_model_id: UUID,
        input_dto: UpdateProviderModelInput,
    ) -> ProviderModelOutput:
        item = await self._provider_model_repo.get_by_id(provider_model_id)
        if item is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        data = input_dto.model_dump(exclude_unset=True)
        if "provider_credential_id" in data:
            credential = await self._load_credential(
                data["provider_credential_id"],
                item.project_id,
            )
            item.provider_credential_id = credential.id
        else:
            credential = await self._load_credential(
                item.provider_credential_id,
                item.project_id,
            )
        if "name" in data and data["name"] is not None:
            item.name = data["name"].strip()
        if "model" in data and data["model"] is not None:
            item.model = data["model"].strip()
        if "metadata" in data and data["metadata"] is not None:
            item.metadata = data["metadata"] or {}
        if "status" in data and data["status"] is not None:
            item.status = data["status"]
        if not item.name:
            raise ValidationError("Provider model name is required")
        if not item.model:
            raise ValidationError("Provider model identifier is required")
        saved = await self._provider_model_repo.update(item)
        return _provider_model_to_output(saved, credential.provider)

    async def _load_credential(self, credential_id: UUID, project_id: UUID):
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None or credential.project_id != project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        return credential


class ListProviderModelsUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(
        self,
        input_dto: ListProviderModelsInput,
    ) -> list[ProviderModelOutput]:
        if input_dto.provider_credential_id:
            items = await self._provider_model_repo.list_by_credential(
                input_dto.provider_credential_id
            )
        elif input_dto.project_id:
            items = await self._provider_model_repo.list_by_project(input_dto.project_id)
        else:
            return []
        outputs: list[ProviderModelOutput] = []
        credential_cache = {}
        for item in items:
            credential = credential_cache.get(item.provider_credential_id)
            if credential is None:
                credential = await self._credential_repo.get_by_id(
                    item.provider_credential_id
                )
                credential_cache[item.provider_credential_id] = credential
            outputs.append(
                _provider_model_to_output(
                    item,
                    getattr(credential, "provider", None),
                )
            )
        return outputs


class GetProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(self, provider_model_id: UUID) -> ProviderModelOutput:
        item = await self._provider_model_repo.get_by_id(provider_model_id)
        if item is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        credential = await self._credential_repo.get_by_id(item.provider_credential_id)
        return _provider_model_to_output(item, getattr(credential, "provider", None))


def _provider_model_to_output(item: ProviderModel, provider=None) -> ProviderModelOutput:
    return ProviderModelOutput(
        id=item.id,
        project_id=item.project_id,
        provider_credential_id=item.provider_credential_id,
        provider=provider,
        name=item.name,
        model=item.model,
        status=item.status,
        metadata=item.metadata,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
