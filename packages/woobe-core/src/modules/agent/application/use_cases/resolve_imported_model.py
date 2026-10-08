from modules.agent.application.dtos.imported_model_dtos import ResolveImportedModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
    _provider_model_to_output,
)
from modules.agent.application.use_cases.inspect_provider_model_definition import (
    InspectProviderModelDefinitionUseCase,
)
from shared.contracts.errors import ValidationError


class ResolveImportedModelUseCase:
    """Recheck approved identity under owner row locks before reuse or creation."""

    def __init__(self, models, credentials):
        self._models, self._credentials = models, credentials
        self._create = CreateProviderModelUseCase(models, credentials)
        self._inspect = InspectProviderModelDefinitionUseCase(self._create, models)

    async def execute(self, input_dto: ResolveImportedModelInput):
        credential = await self._credentials.lock_by_id(
            input_dto.provider_credential_id
        )
        if credential is None or credential.project_id != input_dto.project_id:
            raise ValidationError("Destination credential is unavailable")
        if input_dto.expected_credential_revision is not None and (
            credential.updated_at is None
            or credential.updated_at.isoformat()
            != input_dto.expected_credential_revision
        ):
            raise ValidationError("Destination credential changed after approval")
        if input_dto.expected_model_id is not None:
            await self._models.lock_by_id(input_dto.expected_model_id)
        inspection = await self._inspect.execute(input_dto)
        expected_id = (
            str(input_dto.expected_model_id) if input_dto.expected_model_id else None
        )
        if (
            inspection["spec_hash"] != input_dto.expected_spec_hash
            or inspection["existing_model_id"] != expected_id
            or inspection["model_revision"] != input_dto.expected_model_revision
        ):
            raise ValidationError("Destination Model identity changed after approval")
        if input_dto.expected_model_id is not None:
            model = await self._models.get_by_id(input_dto.expected_model_id)
            output = _provider_model_to_output(model, credential.provider)
            # Legacy Models may store only metadata. The native inspector already
            # proved full equivalence; expose that canonical effective spec without
            # rewriting a shared historical Model as an import side effect.
            return output.model_copy(
                update={
                    "spec": inspection["spec"],
                    "spec_hash": inspection["spec_hash"],
                    "spec_version": inspection["spec_version"],
                }
            )
        return await self._create.execute(input_dto)
