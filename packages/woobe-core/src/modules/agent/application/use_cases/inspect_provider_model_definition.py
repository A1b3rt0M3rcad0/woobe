from __future__ import annotations

from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.application.interfaces.provider_model_repository import (
    ProviderModelRepository,
)
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.model_spec_compatibility import LegacyModelSpecResolver
from modules.agent.domain.enums import ProviderModelStatus
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from shared.contracts.errors import ValidationError


class InspectProviderModelDefinitionUseCase:
    """Read-only planning uses precisely the owner's model creation validation."""

    def __init__(
        self,
        prepare_model: CreateProviderModelUseCase,
        repository: ProviderModelRepository,
    ):
        self._prepare_model, self._repository = prepare_model, repository

    async def execute(self, input_dto: CreateProviderModelInput) -> dict:
        proposed, credential = await self._prepare_model.prepare(input_dto)
        proposed_spec = ModelSpec.from_dict(proposed.spec)
        if (
            proposed_spec.provider != str(credential.provider)
            or proposed_spec.model_id != proposed.model
            or (
                input_dto.model_type
                and proposed_spec.model_type != input_dto.model_type
            )
        ):
            raise ValidationError(
                "ModelSpec identity differs from the destination Model"
            )
        reused = None
        for candidate in await self._repository.list_by_credential(credential.id):
            if (
                candidate.project_id != proposed.project_id
                or candidate.provider_credential_id != credential.id
                or candidate.model != proposed.model
                or str(candidate.status) != ProviderModelStatus.active.value
            ):
                continue
            spec = (
                ModelSpec.from_dict(candidate.spec)
                if candidate.spec is not None
                else LegacyModelSpecResolver().resolve(
                    candidate, provider=str(credential.provider)
                )
            )
            digest = model_spec_hash(spec)
            if candidate.spec_hash is not None and candidate.spec_hash != digest:
                continue
            if digest == model_spec_hash(proposed_spec):
                reused = candidate
                break
        return {
            "provider": str(credential.provider),
            "model": proposed.model,
            "model_type": proposed.model_type,
            "spec": proposed.spec,
            "spec_version": proposed.spec_version,
            "spec_hash": proposed.spec_hash,
            "credential_id": str(credential.id),
            "existing_model_id": str(reused.id) if reused else None,
            "credential_revision": credential.updated_at.isoformat()
            if credential.updated_at
            else None,
            "model_revision": reused.updated_at.isoformat()
            if reused and reused.updated_at
            else None,
        }
